import logging
import random

from google.appengine.api import mail
from google.appengine.api import taskqueue

from dateutil import *
from model import *

from django.conf import settings

from utilities.mandrill import * 
from utilities import framework

REMINDER = """
Hey!

Your teammates want to know what you're up to. Don't leave 'em hanging.

Simply respond to this email with...
- highs and lows for last week
- plans for upcoming week
- any obstacles or challenges in your path

Feel free to link to wiki pages, designs, Google Docs or Github commits. Snippets are due by Monday at 7pm.

Hugs,
Snippets
"""

FINAL_REMINDER = """
Just a heads up, your snippet is due by 7pm today.
"""

MISSED_SNIPPETS = """
Hey there,

We all know that sometimes you have a few too many things to do and you run out
of time to submit a snippet. Don't sweat it -- every week you get another chance
to reflect and share your work!
"""

class MissedEmail(framework.BaseHandler):
    def get(self):
        d = date_for_missed_snippets()
        all_users = User.all().filter("enabled =", True).fetch(500)
       
        for user in all_users:
            if user.email in submitted_users(d):
                logging.info("Submitted: " + user.email) 
            else:
                all_followers = "no_followers"
                followers = list()
                for f in all_users:
                    if user.enabled == True and user.email in f.following:
                        followers.append(f.email.split('@')[0])

                if followers:
                    all_followers = ','.join(map(str, followers)) 
        
                taskqueue.add(url='/onemissed', params={
                        'email': user.email,
                        'all_followers': all_followers
                        })

class OneMissedEmail(framework.BaseHandler):
    def post(self):
        email = self.request.get('email')
        all_followers = self.request.get('all_followers')
       
        if all_followers != "no_followers":
            followers = [f.encode('UTF8') for f in all_followers.split(',')]
            remaining_followers = len(followers) - 1

            subject = ':( :( :( %s and %s others missed hearing from you!' % ( 
                    random.choice(followers), 
                    remaining_followers)
       
            # this is super hacky; i'm not proud of this
            subject = subject.replace(" and 0 others", "")
            subject = subject.replace("1 others", "1 other")
        
            follower_intro = "And just in case you were curious, these folks are looking forward to it:"
            body = '%s\n%s\n%s\n\n%s' % (
                    MISSED_SNIPPETS, 
                    follower_intro, 
                    all_followers.replace(',',', '),
                    'Hugs,\nSnippets')

        else:
            subject = ":( :( :( We missed hearing from you!"
            body = '%s\n%s' % (
                    MISSED_SNIPPETS,
                    'Hugs,\nSnippets')

        MandrillEmail.email(
            email,
            None,
            subject,
            ['snippets', ],
            body,
            None 
        )

    def get(self):
        self.post()

class ReminderEmail(framework.BaseHandler):
    def get(self):
        d = date_for_retrieval()
        all_users = User.all().filter("enabled =", True).fetch(500)
        
        for user in all_users:
            if user.email in submitted_users(d):
                logging.info("Submitted: " + user.email) 
            else:
                taskqueue.add(url='/onereminder', params={
                    'email': user.email,
                    'final': self.request.get('final')
                    })

class OneReminderEmail(framework.BaseHandler):
    def post(self):
        body = REMINDER
        subject = "Snippet time!"
        email = self.request.get('email')
        if self.request.get('final') == "true":
            subject = "Re: " + subject 
            body = FINAL_REMINDER
        else:
            desired_user = user_from_email(email)
            snippets = desired_user.snippet_set
            snippets = sorted(snippets, key=lambda s: s.date, reverse=True)

            if snippets:
                last_snippet = 'Week of %s\n%s\n%s' % (snippets[0].date, '-' * 30,
                        snippets[0].text)
                ps = "PS. I've included your most recent snippet below to help you get started."
                body = '%s\n%s\n\n%s' % (body, ps, last_snippet)

        MandrillEmail.email(
            email,
            None,
            subject,
            ['snippets', ],
            body,
            None 
        )

    def get(self):
        self.post()


class DigestEmail(framework.BaseHandler):
    def get(self):
        all_users = User.all().filter("enabled =", True).fetch(500)
        for user in all_users:
            taskqueue.add(url='/onedigest', params={'email': user.email})


class OneDigestEmail(framework.BaseHandler):
    def __send_mail(self, recipient, body):
        MandrillEmail.email(
            recipient,
            None,
            "Snippet delivery!",
            ['snippets', ],
            body,
            None 
        )

    def __snippet_to_text(self, snippet):
        divider = '-' * 30
        return '%s\n%s\n%s' % (snippet.user.pretty_name(), divider, snippet.text)

    def get(self):
        self.post()

    def post(self):
        user = user_from_email(self.request.get('email'))
        d = date_for_retrieval()
        all_snippets = Snippet.all().filter("date =", d).fetch(500)
        all_users = User.all().fetch(500)
        following = compute_following(user, all_users)
        logging.info(all_snippets)
        body = '\n\n'.join([self.__snippet_to_text(s) for s in all_snippets if s.user.email in following])
        if body:
            following_users = [u.encode('UTF8') for u in user.following]
            missing = set()
            for u in following_users:
                desired_user = user_from_email(u)
                if desired_user.enabled == True:
                    if u not in submitted_users(d):
                        missing.add(u.split('@')[0])
            title = 'For the week of %s\n%s' % (d, '-' * 50)
            if missing:
                title += '\nNo snippets from: %s' % (", ".join(missing))
            body = '%s\n%s\n\n\n%s' % (title, settings.SITE_DOMAIN, body)
            self.__send_mail(user.email, body)
        else:
            logging.info(user.email + ' not following anybody.')
