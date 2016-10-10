#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from model import *
from dateutil import *
import hashlib
from utilities import framework
from utilities import authorized
import logging
import urllib



class UserHandler(framework.BaseHandler):
    """Show a given user's snippets."""

    @authorized.role('user')
    def get(self, email):
        user = self.get_user()

        # Update enabled state if requested
        set_enabled = self.request.get('setenabled')
        if set_enabled == '1':
            user.enabled = True
            user.put()
        elif set_enabled == '0':
            user.enabled = False
            user.put()

        # Update tags if sent
        tags = self.request.get('tags')
        if tags:
            user.tags = [s.strip() for s in tags.split(',')]
            user.put()


        email = urllib.unquote_plus(email)
        email_md5 = hashlib.md5(email).hexdigest()
        desired_user = user_from_email(email)
        snippets = desired_user.snippet_set
        snippets = sorted(snippets, key=lambda s: s.date, reverse=True)
        following = email in user.following
        tags = [(t, t in user.tags_following) for t in desired_user.tags]

        if user.email == desired_user.email:
            owner = True
        else:
            owner = False

        template_values = {
                           'current_user': user,
                           'user': desired_user,
                           'email_md5': email_md5,
                           'owner': owner,
                           'snippets': snippets,
                           'following': following,
                           'tags': tags
                           }
        self.render('user', template_values)


class FollowHandler(framework.BaseHandler):
    """Follow a user or tag."""
    @authorized.role('user')
    def get(self):
        user = self.get_user()
        desired_tag = self.request.get('tag')
        desired_user = self.request.get('user')
        continue_url = self.request.get('continue')

        if desired_tag and (desired_tag not in user.tags_following):
            user.tags_following.append(desired_tag)
            user.put()
        if desired_user and (desired_user not in user.following):
            user.following.append(desired_user)
            user.put()

        self.redirect(continue_url)


class UnfollowHandler(framework.BaseHandler):
    """Unfollow a user or tag."""
    @authorized.role('user')
    def get(self):
        user = self.get_user()


        desired_tag = self.request.get('tag')
        desired_user = self.request.get('user')
        continue_url = self.request.get('continue')

        if desired_tag and (desired_tag in user.tags_following):
            user.tags_following.remove(desired_tag)
            user.put()
        if desired_user and (desired_user in user.following):
            user.following.remove(desired_user)
            user.put()

        self.redirect(continue_url)


class TagHandler(framework.BaseHandler):
    """View this week's snippets in a given tag."""
    @authorized.role('user')
    def get(self, tag):
        user = self.get_user()
        d = date_for_retrieval()
        all_snippets = Snippet.all().filter("date =", d).fetch(500)
        if (tag != 'all'):
            all_snippets = [s for s in all_snippets if tag in s.user.tags]
        following = tag in user.tags_following

        template_values = {
                           'current_user': user,
                           'snippets': all_snippets,
                           'following': following,
                           'tag': tag
                           }
        self.render('tag', template_values)


class MainHandler(framework.BaseHandler):
    """Show list of all users and acting user's settings."""

    @authorized.role('user')
    def get(self):
        user = self.get_user()


        # Fetch user list and display
        raw_users = User.all().filter("enabled", True).order('email').fetch(500)
        following = compute_following(user, raw_users)
        all_users = [(u, u.email in following) for u in raw_users]
        all_tags = set()
        for u in raw_users:
            all_tags.update(u.tags)
        all_tags = [(t, t in user.tags_following) for t in all_tags]

        d = date_for_retrieval()
        all_snippets = Snippet.all().filter("date =", d).fetch(500)
        logging.info(all_snippets)
        followed_snippets_raw = [s for s in all_snippets if s.user.email in following]
        followed_snippets = []
        for snippet in followed_snippets_raw:
            followed_snippet ={
                'email_md5':hashlib.md5(snippet.user.email).hexdigest(),
                'text':snippet.text,
                'user':snippet.user
            }
            followed_snippets.append(followed_snippet)
            #followed_snippets[i]['email_md5'] = hashlib.md5(followed_snippets[i].user.email).hexdigest()

        template_values = {
                           'followed_snippets':followed_snippets,
                           'retrieval_date':d,
                           'current_user': user,
                           'all_users': all_users,
                           'all_tags': all_tags
                           }
        self.render('index', template_values)


class NotFoundHandler(framework.BaseHandler):
    def get(self):
        self.write("not found")
