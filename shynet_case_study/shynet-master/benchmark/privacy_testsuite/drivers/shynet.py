import os
from subprocess import Popen, PIPE, STDOUT
from datetime import datetime
from time import sleep
import random
import sqlite3
import requests
import redis
from tools import Task, Subtask
from random import randint
import uuid

from django.apps import apps

class Scenario:

    login_url = "http://127.0.0.1:8000/accounts/login/"
    dashboard_url = "http://127.0.0.1:8000/dashboard/service/{}/"
    ingress_url = "http://127.0.0.1:8000/ingress/{}/script.js"
    consent_url = "http://127.0.0.1:8000/ingress/{}/consent/"
    service = "7407dd77a24f43629f7eadbabb8fbb8a"

    def __init__(self, sc, app_cmd, database, policy, cwd="shynet"):
        self.sc = sc
        self.app_cmd = app_cmd
        self.database = database
        self.count = -1
        self.policy = policy
        self.log_filename = None
        self.cwd = cwd

    def generate_random_session(self):
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        return f'("{uuid.uuid4()}", "", "{date}", "{date}", "Firefox", "Other", "DESKTOP", "Ubuntu", "", "", "", "{self.service}", 0)'
        
    def initialize(self, config):
        """Function to be executed before running the measurements"""
        self.n = config
        pref = f'shynet.initialize (sc={self.sc}, n={self.n})'
        
        with Task(pref, 'Initializing database', cplx=True) as task:
            # print(f"sysyem path {sys.path}")
            with Subtask('Fetching users and sessions', task):
                db = sqlite3.connect(self.database)
                cur = db.cursor()
                users = cur.execute("SELECT id FROM core_user").fetchall()
                services = cur.execute("SELECT uuid FROM core_service").fetchall()
                messages = cur.execute("SELECT uuid FROM analytics_session").fetchall()
                
            if len(users) < 1:
                with Subtask(f'Adding 1 user', task):
                    to_insert = f'(1, "user0", "user0@mail.com", "' + "pbkdf2_sha256$12000$iV0sZ7R8KrVJ$xcIuLw2+ucijlFbCtpRFIy3DxlIANgGjZxJP1pa4kVo=" + '", "0", "0", "firstname", "lastname", "1", "2023-01-01 00:00:00.000000", "token")'
                    cur.execute(f"INSERT INTO core_user (id, username, email, password, is_superuser, is_staff, first_name, last_name, is_active, date_joined, api_token) VALUES {to_insert}")
                    users = cur.execute("SELECT username FROM core_user").fetchall()
                    assert(len(users) == 1)

            if len(services) < 1:
                with Subtask(f'Adding 1 service', task):
                    to_insert = f'("{self.service}", "Service", "2025-04-01 13:02:39.891227", "", "*", "AC", 1, 0, 1, "", "", 0, "")'
                    cur.execute(f"INSERT INTO core_service (uuid, name, created, link, origins, status, owner_id, respect_dnt, collect_ips, ignored_ips, hide_referrer_regex, ignore_robots, script_inject) VALUES {to_insert}")
                    services = cur.execute("SELECT uuid FROM core_service").fetchall()
                    assert(len(services) == 1)

            if len(messages) > self.n:
                with Subtask(f'Deleting {len(messages)-self.n} sessions', task):
                    cur.execute(f"DELETE FROM analytics_session WHERE uuid IN (SELECT uuid FROM analytics_session ORDER BY id DESC LIMIT {len(messages)-self.n})")
                    messages = cur.execute("SELECT uuid FROM analytics_session").fetchall()
                    # print(messages)
                    assert(len(messages) == self.n)
                    
            elif len(messages) < self.n:
                with Subtask(f'Adding {self.n-len(messages)} sessions', task):
                    # print("inside of adding m")
                    to_insert = [self.generate_random_session() for _ in range(len(messages), self.n)]

                    # print(to_insert)
                    cur.execute(f"INSERT INTO analytics_session (uuid, identifier, start_time, last_seen, browser, device, device_type, os, asn, country, time_zone, service_id, is_bounce) VALUES {', '.join(to_insert)}")
                    messages = cur.execute("SELECT uuid FROM analytics_session").fetchall()
                    assert(len(messages) == self.n)
            
            with Subtask('Committing and closing database', task):
                cur.close()
                db.commit()
                db.close()
                
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f'logs/{timestamp}_{self.sc}_{self.policy}.log'
        self.log_filename = log_filename
        self.start_process()
        
    def start_process(self):  
        pref = f'shynet.initialize (sc={self.sc}, n={self.n})'
        with Task(pref, 'Starting Shynet Django application'):
            with open(self.log_filename, 'a') as log_file:
                try:
                    self.proc = Popen(self.app_cmd, cwd=self.cwd, stdin=PIPE,  stdout=log_file, stderr=STDOUT, text=True)
                    sleep(2)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return None

    def continue_(self):
        """Function to be executed between two instances of the same measurement"""
        pass

    def _user_session(self):
        session = requests.Session()
        r = session.get(self.login_url)
        csrf_token = session.cookies.get('csrftoken')
        login_data = {
            "login": f"user0@mail.com",
            "password": "password",
            "csrfmiddlewaretoken": csrf_token
        }
        r = session.post(self.login_url, data=login_data)
        assert(r.ok)
        return session

    def run(self):
        """Function performing the measurement"""
        if self.sc == 'ingress':
            with Task('shynet.run', 'Measurement for scenario "Ingress"'):
                time_list = []
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                try:
                    session = requests.Session()
                    r = session.get(self.ingress_url.format(self.service), allow_redirects=False)
                    assert(r.ok)
                    t = r.elapsed.total_seconds()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while adding a hit: {e}")
                return {'sc': self.sc, 'n': self.n, 'u': 1, 't': t}

        elif self.sc == 'dashboard':
            with Task('shynet.run', 'Measurement for scenario "Dashboard"'):
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                try:
                    session = self._user_session()
                    r = session.get(self.dashboard_url.format(self.service), allow_redirects=False)
                    assert(r.ok)
                    t = r.elapsed.total_seconds()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while loading the dashboard: {e}")
                return {'sc': self.sc, 'n': self.n, 'u': 1, 't': t}

        elif self.sc == 'consent':
            with Task('shynet.run', 'Measurement for scenario "Consent"'):
                if not self.is_process_running():
                    print("Django server process has terminated")
                    return None
                try:
                    session = requests.Session()
                    r = session.post(self.ingress_url.format(self.service), json={}, allow_redirects=False)
                    assert(r.ok)
                    session_uuid = r.json().get("session")
                    r = session.get(self.consent_url.format(self.service) + f"?session={session_uuid}", allow_redirects=False)
                    assert(r.ok)
                    t = r.elapsed.total_seconds()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while adding a message: {e}")
                return {'sc': self.sc, 'n': self.n, 'u': 1, 't': t}
        
    def finalize(self):
        """Function to be executed after performing the measurements"""
        with Task('shynet.finalize', 'Killing Shynet Django application'):
            self.proc.kill()
             
    def is_process_running(self):
        return self.proc.poll() is None
    
from django.conf import settings
from django.db import connection

class Application:

    app_cmd =  ["python3", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
    database = "shynet/db.sqlite3"

    def start(self, policy):
        """Function to be executed before running any scenarios"""
        with Task('shynet.start', 'Starting evaluation') as task:
            if policy == 'uninstrumented':
                self.database = "benchmark/privacy_testsuite/baseline/shynet/shynet/db.sqlite3"

            with Subtask('Opening database', task):
                db = sqlite3.connect(self.database)
                cur = db.cursor()
                
            with Subtask('Cleaning database', task):
                cur.execute("DELETE FROM core_user WHERE 1=1")
                cur.execute("DELETE FROM core_service WHERE 1=1")
                cur.execute("DELETE FROM analytics_session WHERE 1=1")
                cur.execute("DELETE FROM analytics_hit WHERE 1=1")
                cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('auth_user', 'analytics_session', 'analytics_hit')")
                
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
        with Task('shynet.stop', 'Stopping evaluation'):
            pass
            
    def scenarios(self, policy):
        """Return the list of available scenarios"""
        with Task('shynet.scenarios', 'Computing scenarios'):
            if policy == 'uninstrumented':
                cwd  = "benchmark/privacy_testsuite/baseline/shynet/shynet"

                scenarios = [
                    Scenario('ingress', self.app_cmd, self.database, policy, cwd=cwd),
                    Scenario('dashboard', self.app_cmd, self.database, policy, cwd=cwd),
                ]
            else:
                scenarios = [
                    Scenario('ingress', self.app_cmd, self.database, policy),
                    Scenario('dashboard', self.app_cmd, self.database, policy),
                    Scenario('consent', self.app_cmd, self.database, policy),
                ]
        return scenarios

    def configurations(self):
        """Return the list of available parameter configurations"""
        with Task('shynet.configurations', 'Computing configurations'):
            # n: number of messages
            N_n = 1000
            ns = [10**i for i in range(2, 7)]
            # configs = ns
            configs = ns

        return configs
    
    def dep_vars(self):
        """Return the list of the dependent vars in the results"""
        return ["t"]

    def indep_vars(self):
        """Return the list of the independent vars in the results"""
        return ["sc", "n"]
