__author__ = "yparfenov"

from Gigatest.lib.helper import HelperMethods as helper
from Gigatest.lib.helper import Mongo
from Gigatest.lib import gutils
from Gigatest.lib.templates import Templates
import importlib
import sys
import os, traceback
import re
import yaml
import time
import json

SUITE_STATUS = ['PROVISIONING', 'READY', 'STARTED', 'FINISHED', 'ABORTED', 'ERROR']
TEST_STATUS = ['PROVISIONING', 'READY', 'STARTED', 'FINISHED', 'ABORTED', 'ERROR', 'COMPLETE']

class TestSuite:
    @staticmethod
    def add_suite(runid, suite, logger=None, db=None):
        #self.args = args
        #test_suite_details = self.test_suite_details_template  # self.args #TESTRUN_DETAILS_TEMPLATE
        test_suite_details_template = Templates.SUITE_DETAILS_TEMPLATE
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        test_suite_details_template['runid'] = runid
        test_suite_details_template['status'] = 'PROVISIONING'
        test_suite_details_template['suitename'] = suite['longname']
        test_suite_details_template['suitemetadata'] = suite
        #test_run_details['pid'] = os.getpid()
        #test_run_details['runid'] = test_run_details['run-tag']
        #if '__TESTSUITE_LABEL__' in self.args['custom_params']: self.test_suite_details_template['suitelabel'] = self.args['custom_params']['__TESTSUITE_LABEL__']

        if logger:
            logger.info ("runid {}: adding test suite {}". format(runid, suite['longname']))
        # Add suite to MongoDB
        if db:
            db.update_db(runid, {'$addToSet': {'suites': suite_name}}, collection='testsuites')
        else:
            with Mongo('testsuites') as testsuites:
                testsuites.add_to_db(runid, test_suite_details_template)

    @staticmethod
    def update_suite(runid, suite, logger=None, db=None, **kwargs):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')

        #select proper suite
        selector = {'$and':[{'runid':runid},{'suitename':suite['longname']}]}

        if logger:
            logger.info ("runid {}: updating test suite {}". format(runid, suite['longname']))
        # Add suite to MongoDB
        if db:
            db.update_db(selector, {'$set': {'suitemetadata': suite}}, collection='testsuites')
            if kwargs:
                db.update_db(selector, {'$set': kwargs}, collection='testsuites')
        else:
            with Mongo('testsuites') as testsuites:
                testsuites.update_db(selector, {'$set': {'suitemetadata':suite}})
                if kwargs:
                    testsuites.update_db(selector, {'$set': kwargs})


class TestCase:
    @staticmethod
    def add_test(runid, suite_name, test_name, test, logger=None, db=None, sqn=None):
        # self.args = args
        # test_suite_details = self.test_suite_details_template  # self.args #TESTRUN_DETAILS_TEMPLATE
        test_case_details_template = Templates.TEST_CASE_TEMPLATE
        try:
            runid = int(runid)
        except:
            raise Exception('runid must be either int or str convertable to int')
        test_case_details_template['runid'] = runid
        test_case_details_template['testname'] = test_name
        test_case_details_template['longname'] = test['longname']
        test_case_details_template['status'] = 'PROVISIONING'
        test_case_details_template['suite'] = suite_name
        test_case_details_template['testmetadata'] = test
        if sqn: test_case_details_template['sqn'] = sqn

        if logger:
            logger.info("runid {}: adding test case {}".format(runid, test_name))
        # Add test to MongoDB
        if db:
            db.add_to_db(runid, test_case_details_template, collection='testcases')
            if db.count_docs({'$and':[{'runid':runid},{'suitename': suite_name}]}, collection='testsuites') > 0:
                db.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$addToSet':{'tests':test_name}}, collection='testsuites')
        else:
            with Mongo('testcases') as testcases:
                testcases.add_to_db(runid, test_case_details_template)
            # Add test to suite record to MongoDB
            with Mongo('testsuites') as testsuites:
                if testsuites.count_docs({'$and':[{'runid':runid},{'suitename': suite_name}]}) > 0:
                    testsuites.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$addToSet':{'tests':test_name}})

    @staticmethod
    def update_test(runid, suite_name, test_name, test, logger=None, db=None, **kwargs):
        try:
            runid = int(runid)
        except:
            raise Exception('runid must be either int or str convertable to int')
        #test_case_details_template['runid'] = runid
        #test_case_details_template['testname'] = test_name
        #test_case_details_template['status'] = 'PROVISIONING'
        #test_case_details_template['suite'] = suite_name
        #test_case_details_template['testmetadata'] = test

        if logger:
            logger.info("runid {}: updating test case {}".format(runid, test_name))
        # Add test to MongoDB
        if db:
            db.update_db ({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]},
                                  {'$set':{'testmetadata':test}}, collection='testcases')
            if kwargs:
                db.update_db({'$and': [{'runid': runid}, {'suite': suite_name}, {'testname': test_name}]},
                                     {'$set': kwargs}, collection='testcases')
        else:
            with Mongo('testcases') as db:
                db.update_db ({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]},
                                      {'$set':{'testmetadata':test}})
                if kwargs:
                    db.update_db({'$and': [{'runid': runid}, {'suite': suite_name}, {'testname': test_name}]},
                                         {'$set': kwargs})

    @staticmethod
    def get_testcase_stats (runid, db):
        run_status = {}
        run_status['num_of_completed'] = db.count_docs({'$and': [{'runid': runid}, {'status': 'COMPLETE'}]},
                                                         collection='testcases')
        run_status['num_of_in_progress'] = db.count_docs({'$and': [{'runid': runid}, {'status': 'STARTED'}]},
                                                           collection='testcases')
        num_of_idle = db.count_docs({'$and': [{'runid': runid}, {'status': 'READY'}]},
                                                         collection='testcases')
        run_status['num_of_fail'] = db.count_docs(
            {'$and': [{'runid': runid}, {'status': 'COMPLETE'}, {'result': 'FAIL'}]},
            collection='testcases')
        run_status['num_of_pass'] = db.count_docs(
            {'$and': [{'runid': runid}, {'status': 'COMPLETE'}, {'result': 'PASS'}]},
            collection='testcases')
        run_status['num_of_skip'] = run_status['num_of_completed'] - run_status['num_of_fail'] - run_status[
            'num_of_pass']
        run_status['num_of_testcases'] = run_status['num_of_completed'] + run_status['num_of_in_progress'] + num_of_idle
        return run_status

    @staticmethod
    def add_kw(runid, suite_name, test_name, kw_name, kw, logger=None, db=None, sqn=None):
        # self.args = args
        # test_suite_details = self.test_suite_details_template  # self.args #TESTRUN_DETAILS_TEMPLATE
        if not test_name:
            test_name = ""
        kw_template = Templates.KW_TEMPLATE
        try:
            runid = int(runid)
        except:
            raise Exception('runid must be either int or str convertable to int')
        kw_template['runid'] = runid
        kw_template['kwname'] = kw_name
        kw_template['status'] = 'PROVISIONING'#kw['status']
        kw_template['suite'] = suite_name
        kw_template['test'] = test_name
        #kw_template['type'] = kw['type']
        kw_template['kwmetadata'] = kw
        if sqn: kw_template['sqn'] = sqn

        if logger:
            logger.info("runid {}: adding kw {}".format(runid, kw_template['kwname']))

        # Add kw to MongoDB
        if db:
            if db.count_docs({'$and':[{'runid':runid},{'suite':suite_name},{'test': test_name}, {'kwname':kw_name}]}, collection='kws') > 0: return 0
            db.add_to_db(runid, kw_template, collection='kws')
        else:
            with Mongo('kws') as kws:
                if kws.count_docs({'$and':[{'runid':runid},{'suite':suite_name},{'test': test_name}, {'kwname':kw_name}]}) > 0: return 0
                kws.add_to_db(runid, kw_template)

        # Add kw to test case or suite MongoDB record
        if test_name:
            if db:
                if db.count_docs({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}, collection='testcases') > 0:
                    if 'SETUP' in kw['type']:
                        db.update_db({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}, {'$set':{'setup':kw_template['kwname']}}, collection='testcases')
                    elif 'TEARDOWN' in kw['type']:
                        db.update_db({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}, {'$set': {'teardown': kw_template['kwname']}}, collection='testcases')
                    else:
                        db.update_db({'$and':[{'runid':runid},{'suite':suite_name}, {'testname': test_name}]}, {'$addToSet': {'kws': kw_template['kwname']}}, collection='testcases')
            else:
                with Mongo('testcases') as testcases:
                    if testcases.count_docs({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}) > 0:
                        if 'SETUP' in kw['type']:
                            testcases.update_db({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}, {'$set':{'setup':kw_template['kwname']}})
                        elif 'TEARDOWN' in kw['type']:
                            testcases.update_db({'$and':[{'runid':runid},{'suite':suite_name},{'testname': test_name}]}, {'$set': {'teardown': kw_template['kwname']}})
                        else:
                            testcases.update_db({'$and':[{'runid':runid},{'suite':suite_name}, {'testname': test_name}]}, {'$addToSet': {'kws': kw_template['kwname']}})
        else:
            if db:
                if db.count_docs({'$and':[{'runid':runid},{'suitename': suite_name}]}, collection='testsuites') > 0:
                    #if collection.count_docs(runid, {'testname': test_name}) > 0:
                    if 'SETUP' in kw['type']:
                        db.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$set': {'setup': kw_template['kwname']}}, collection='testsuites')
                    elif 'TEARDOWN' in kw['type']:
                        db.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$set': {'teardown': kw_template['kwname']}}, collection='testsuites')
                    else:
                        db.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$addToSet': {'kws': kw_template['kwname']}}, collection='testsuites')

            else:
                with Mongo('testsuites') as testsuites:
                    if testsuites.count_docs({'$and':[{'runid':runid},{'suitename': suite_name}]}) > 0:
                        #if testsuites.count_docs(runid, {'testname': test_name}) > 0:
                        if 'SETUP' in kw['type']:
                            testsuites.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$set': {'setup': kw_template['kwname']}})
                        elif 'TEARDOWN' in kw['type']:
                            testsuites.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$set': {'teardown': kw_template['kwname']}})
                        else:
                            testsuites.update_db({'$and':[{'runid':runid},{'suitename': suite_name}]}, {'$addToSet': {'kws': kw_template['kwname']}})


    @staticmethod
    def update_kw(runid, suite_name, test_name, kw_name, kw, logger=None, db=None, **kwargs):#status=None):
        try:
            runid = int(runid)
        except:
            raise Exception('runid must be either int or str convertable to int')
        if not test_name:
            test_name = ""
        #test_case_details_template['runid'] = runid
        #test_case_details_template['testname'] = test_name
        #test_case_details_template['status'] = 'PROVISIONING'
        #test_case_details_template['suite'] = suite_name
        #test_case_details_template['testmetadata'] = test

        if logger:
            logger.info("runid {}: updating {}".format(runid, kw_name))
        # Add test to MongoDB
        if db:
            db.update_db ({'$and':[{'runid':runid},{'suite':suite_name},{'test': test_name},{'kwname':kw_name}]},
                                  {'$set':{'kwmetadata':kw}}, collection='kws')
            if kwargs:
                db.update_db({'$and': [{'runid': runid}, {'suite': suite_name}, {'test': test_name},{'kwname':kw_name}]},
                                     {'$set': kwargs}, collection='kws')#{'status': status}})

        else:
            with Mongo('kws') as kws:
                kws.update_db ({'$and':[{'runid':runid},{'suite':suite_name},{'test': test_name},{'kwname':kw_name}]},
                                      {'$set':{'kwmetadata':kw}})
                if kwargs:
                    kws.update_db({'$and': [{'runid': runid}, {'suite': suite_name}, {'test': test_name},{'kwname':kw_name}]},
                                         {'$set': kwargs})#{'status': status}})




