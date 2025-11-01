import os
from subprocess import Popen, PIPE, STDOUT
from datetime import datetime
from time import sleep
import random
import sqlite3
import requests
import redis
from lorem_text import lorem
from tools import Task, Subtask
from random import randint

from django.apps import apps

class Scenario:

    login_url = "http://127.0.0.1:8000/accounts/login/"
    timeline_url = "http://127.0.0.1:8000/"
    add_message_url = "http://127.0.0.1:8000/post/twit/"
    delete_message_url = "http://127.0.0.1:8000/twit/delete/"
    set_cookies_url = "http://127.0.0.1:8000/set-cookie-consent/"

    def __init__(self, sc, app_cmd, database, policy):
        self.sc = sc
        self.app_cmd = app_cmd
        self.database = database
        self.count = -1
        self.policy = policy
        self.log_filename = None

    def generate_random_message(self, users):
        author = random.choice(users)[0]
        text = lorem.paragraph()
        date = int(round(datetime.now().timestamp()))
        if len(text) > 140:
                scenarios = [
                    Scenario('timeline', self.app_cmd, self.database, self.policy),
                    Scenario('consent_timeline', self.app_cmd, self.database, self.policy),
                ]
        else:
            text = text[:137] + '...'
        return f'("{text}", "{date}", "{date}", "{author}", "{date}", "{date}")'
        
    def initialize(self, config):
        """Function to be executed before running the measurements"""
        self.u, self.n = config
        pref = f'minitwit.initialize (sc={self.sc}, u={self.u}, n={self.n})'
        
        with Task(pref, 'Initializing database', cplx=True) as task:
            # print(f"sysyem path {sys.path}")
            with Subtask('Fetching users and tweets', task):
                db = sqlite3.connect(self.database)
                cur = db.cursor()
                users = cur.execute("SELECT id FROM auth_user").fetchall()
                messages = cur.execute("SELECT id FROM twitt_twit").fetchall()
                # print(f"users {users} messages {messages}")
            if len(users) > self.u:
                with Subtask(f'Deleting {len(users)-self.u} users', task):
                    cur.execute(f"DELETE FROM auth_user WHERE id IN (SELECT id FROM auth_user ORDER BY id DESC LIMIT {len(users)-self.u})")
                    users = cur.execute("SELECT id FROM auth_user").fetchall()
                    assert(len(users) == self.u)

            elif len(users) < self.u:
                with Subtask(f'Adding {self.u-len(users)} users', task):
                    to_insert = [f'("user{i}", "user{i}@mail.com", "' + "pbkdf2_sha256$12000$iV0sZ7R8KrVJ$xcIuLw2+ucijlFbCtpRFIy3DxlIANgGjZxJP1pa4kVo=" + '", "0", "0", "firstname", "lastname", "1", "2023-01-01 00:00:00.000000")'
                                for i in range(len(users), self.u)]
                    cur.execute(f"INSERT INTO auth_user (username, email, password, is_superuser, is_staff, first_name, last_name, is_active, date_joined) VALUES {','.join(to_insert)}")
                    users = cur.execute("SELECT username FROM auth_user").fetchall()
                    assert(len(users) == self.u)

            if len(messages) > self.n:
                with Subtask(f'Deleting {len(messages)-self.n} messages', task):
                    cur.execute(f"DELETE FROM twitt_twit WHERE id IN (SELECT id FROM twitt_twit ORDER BY id DESC LIMIT {len(messages)-self.n})")
                    messages = cur.execute("SELECT id FROM twitt_twit").fetchall()
                    # print(messages)
                    assert(len(messages) == self.n)
                    
            elif len(messages) < self.n:
                with Subtask(f'Adding {self.n-len(messages)} messages', task):
                    # print("inside of adding m")
                    to_insert = [self.generate_random_message(users) for _ in range(len(messages), self.n)]

                    # print(to_insert)
                    cur.execute(f"INSERT INTO twitt_twit (content, posted_on, updated_on, author_id, created_at, lastmodified_at) VALUES {','.join(to_insert)}")
                    messages = cur.execute("SELECT id FROM twitt_twit").fetchall()
                    assert(len(messages) == self.n)
            
            with Subtask('Committing and closing database', task):
                cur.close()
                db.commit()
                db.close()
                
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f'logs/multi_runs/{timestamp}_{self.sc}_{self.policy}.log'
        self.log_filename = log_filename
        self.start_process()
        
    def start_process(self):  
        pref = f'minitwit.initialize (sc={self.sc}, u={self.u}, n={self.n})'
        with Task(pref, 'Starting Minitwit Django application'):
            with open(self.log_filename, 'a') as log_file:
                try:
                    # print(' '.join(self.app_cmd))
                    self.proc = Popen(self.app_cmd, stdin=PIPE,  stdout=log_file, stderr=STDOUT, text=True)
                    sleep(2)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return None

    def continue_(self):
        """Function to be executed between two instances of the same measurement"""
        pass

    def _user_session(self, i):
        session = requests.Session()
        r = session.get(self.login_url)
        csrf_token = session.cookies.get('csrftoken')
        login_data = {
            "username": f"user{i}",
            "password": "password",
            "csrfmiddlewaretoken": csrf_token
        }
        r = session.post(self.login_url, data=login_data)
        assert(r.ok)
        return session

    def _random_user_session(self):
        i = randint(0, self.u - 1)
        return self._user_session(i)

    def run(self):
        """Function performing the measurement"""
        if self.sc == 'add_message':
            with Task('minitwit.run', 'Measurement for scenario "Add message"'):
                time_list = []
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                try:
                    session = self._random_user_session()
                    
                    csrf_token = session.cookies.get('csrftoken')
                    txt = lorem.paragraph()
                    if len(txt) > 140:
                        txt = txt[:137] + '...'
                    data = {
                        "content": txt,
                        "csrfmiddlewaretoken": csrf_token
                    }
                        
                    r = session.post(self.add_message_url, data=data, allow_redirects=False)
                        
                    t = r.elapsed.total_seconds()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while adding a message: {e}")
                return {'sc': self.sc, 'u': self.u, 'n': self.n, 't': t}

        elif self.sc =='timeline':
            with Task('django.run', 'Measurement for scenario "Timeline"'):
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                time_list = []

                try:
                    session = self._random_user_session()

                    r = session.get(self.timeline_url)
                    print(r.text)
                    assert(r.ok)
                    t = r.elapsed.total_seconds()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while loading the timeline: {e}")
                return {'sc': self.sc, 'u': self.u, 'n': self.n,  't': t}

        elif self.sc == 'consent_timeline':
            with Task('django.run', 'Measurement for scenario "Consent"'):
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                time_list = []

                try:
                    session = self._random_user_session()

                    csrf_token = session.cookies.get('csrftoken')
                    data = {
                        "accept": 'true',
                        "csrfmiddlewaretoken": csrf_token
                    }
                    r = session.post(self.set_cookies_url, data=data, allow_redirects=False)
                    t = r.elapsed.total_seconds()

                    return {'sc': self.sc, 'u': self.u, 'n': self.n,  't': t}

                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while adding a message: {e}")
        
    def finalize(self):
        """Function to be executed after performing the measurements"""
        with Task('minitwit.finalize', 'Killing Minitwit Django application'):
            self.proc.kill()
             
    def is_process_running(self):
        return self.proc.poll() is None
    
from django.conf import settings
from django.db import connection

class Application:

    app_cmd =  ["python3", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
    database = "db.sqlite3"

    def start(self, policy):
        """Function to be executed before running any scenarios"""
        with Task('minitwit.start', 'Starting evaluation') as task:
            if policy == 'uninstrumented':
                self.database = "benchmark/privacy_testsuite/baseline/minitwit_django_adapted/db.sqlite3"

            with Subtask('Opening database', task):
                db = sqlite3.connect(self.database)
                cur = db.cursor()
                
            with Subtask('Cleaning database', task):
                cur.execute(f"DELETE FROM auth_user WHERE 1=1")
                cur.execute(f"DELETE FROM twitt_twit WHERE 1=1")
                cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('auth_user', 'twitt_twit')")
                
            with Subtask('Committing and closing database', task):
                cur.close()
                db.commit()
                db.close()
                
            with Subtask('Cleaning redis database', task):
                r = redis.StrictRedis(host='localhost', port=6379, db=0)
                r.flushdb()
                db_size = r.dbsize()
                print(f"Database size: {db_size}")

    def stop(self):
        """Function to be executed after running all scenarios"""
        with Task('minitwit.stop', 'Stopping evaluation'):
            pass
            
    def scenarios(self, policy):
        """Return the list of available scenarios"""
        with Task('minitwit.scenarios', 'Computing scenarios'):
            if policy == 'uninstrumented':
                self.app_cmd  = ["python3", "benchmark/privacy_testsuite/baseline/minitwit_django_adapted/manage.py", "runserver", "127.0.0.1:8000", "--noreload"]

            scenarios = [
                Scenario('add_message', self.app_cmd, self.database, policy),
                Scenario('timeline', self.app_cmd, self.database, policy),
                Scenario('consent_timeline', self.app_cmd, self.database, policy),
            ]
        return scenarios

    def configurations(self):
        """Return the list of available parameter configurations"""
        with Task('minitwit.configurations', 'Computing configurations'):
            # n: number of messages
            N_n = 1000
            ns = [10**i for i in range(2, 7)] 
            # up: number of users
            N_u = 1000
            us = [10,100,1000] # add points: 5000, 100000(?)
            # configs = us x ns
            configs = [(N_u, n) for n in ns]# + [(N_n, u) for u in us]

        return configs
    
    def dep_vars(self):
        """Return the list of the dependent vars in the results"""
        return ["t"]

    def indep_vars(self):
        """Return the list of the independent vars in the results"""
        return ["sc", "u", "n"]
