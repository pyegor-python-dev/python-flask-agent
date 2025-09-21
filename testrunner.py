
__author__ = "yparfenov"
import os, sys, traceback
from Gigatest.lib import gutils
import importlib
#import sys
import re
import yaml
import time
import json
#import numbers
import uuid
from datetime import datetime, timedelta
from multiprocessing import Process
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr

# from contextlib import closingr
# from IPython.utils.io import Tee
#from .gigalogger import Log
from Gigatest.lib.helper import HelperMethods as helper
from Gigatest.lib.helper import Mongo
from Gigatest.lib.templates import Templates
from lib.constants import Constants

def remove_dots_from_keys(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_key = key.replace('.', '__')  # Replace dot with underscore
            new_dict[new_key] = remove_dots_from_keys(value)
        return new_dict
    elif isinstance(obj, list):
        return [remove_dots_from_keys(item) for item in obj]
    else:
        return obj


class TestRunner(Process):
# '''
# curl -X GET "http://10.116.1.46/get_testrun_detail/7568770" -H "accept: application/json"
# {
#   "testrun_details": {
#     "runid": "7568770",
#     "suitename": "/home/automation/fm_auto_test/tools/runReg",
#     "suitelabel": "fm_cloud_nsxt_post",
#     "status": "STARTED",
#     "pid": "2162574",
#     "testcases": [
#       "Validate and Verify Traffic for map tep : Vseries Hostbased DHCP IP Node deployment with Small formFactor",
#       "Validate and Verify Traffic for map tep : Vseries CLUSTERED Static IP Node deployment with Small formFactor",
#       "Validate and Verify Traffic for map tep : Vseries CLUSTERED DHCP IP Node deployment with Medium formFactor",
#       "Validate and Verify Traffic for map tep : Vseries CLUSTERED Static IP Node deployment with Medium formFactor",
#       "Validate and Verify Traffic for map tep : Vseries HOST_BASED Static IP Node deployment with Small formFactor",
#       "Validate and Verify Traffic for map app == slicing tep : Vseries HOSTBASED DHCP IP Node deployment with Large formFactor",
#       "Validate and Verify Traffic for map app == masking tep : Vseries CLUSTERED Static IP Node deployment with Large formFactor"
#     ],
#     "updated_datetime": "Thu, 11 Apr 2024 13:31:21 -0000",
#     "created_datetime": "Thu, 11 Apr 2024 13:31:18 -0000"
#   }
# }
    def __init__(self, args, log_path):
        super(TestRunner, self).__init__()
        self.args = args
        self.log_path = log_path #helper.get_logger(log_path, 'runner.log')


    def run(self):
        self._runner()

    def _runner (self):
        #logger = helper.get_logger(self.log_path, 'runner.log')
        self.logger = helper.get_logger(self.log_path, 'runner.log')
        if 'run-tag' not in self.args: raise Exception('run-tag in testrun payload is not defined')
        if not self.args['run-tag']: raise Exception('run-tag in testrun payload is 0')
        self.delete_legacy_records()
        self.add_testrun()

        try:
            with open("{}/gigagent.log".format(self.log_path), "w+") as f:
                with redirect_stdout(f), redirect_stderr(f):
                    ### Test run preparation ###
                    if 'taf' in self.args['test_type'] or 'robot' in self.args['test_type']:
                        self.logger.info("Export TAF env. variables {}".format(self.args['test_param'][1]['envar']))
                        helper.export_taf_envvar(self.args)
                        robot_args = self.get_taf_robot_params()
                        self.args['test_param'].append({'robot': robot_args})
                    else:
                        robot_args = {'robot': []}
                        self.args['test_param'].append({'robot': []})
                    self.logger.info("Append Robot params to test_param: {}".format(robot_args))
                    self.add_robot_params (robot_args)
                    ### Test run ###
                    self.start_taf_run()
        except Exception as e:
            self.logger.error('Testrun exception: {} traceback = {}'.format( e, helper.get_traceback ()))
            TestRun.update_testrun(int(self.args['run-tag']), status='FINISHED', ended_time=datetime.now(), result='FAIL')
            TestRun.call_back_complete(int(self.args['run-tag']))

    def add_testrun(self):
        if not self.args:
            raise Exception ("no args defined for 'add_testrun' method")
        #log_path = args['log-path']
        test_type = self.args['test_type']
        env_vars = {"__LogDir__":self.log_path,"USER_LIB_PATH":self.args['library_path'],"LOG_URL":"http://{}/browse_dir?path={}".format(helper.get_server_ip(), os.path.join(self.log_path, 'log.html'))}
        self.logger.info("Exporting env variables {}".format(env_vars))
        helper.export_env_vars(env_vars)
        swversion = ''
        if 'custom_params' in self.args:
            if '__SWVersion__' in self.args['custom_params']:
                swversion = self.args['custom_params']['__SWVersion__']

        if swversion:
            #os.environ["__SWVersion__"] = swversion
            self.logger.info("Exporting env variables {}".format({"__SWVersion__":swversion}))
            helper.export_env_vars({"__SWVersion__":swversion})
        else:
            helper.export_env_vars({"__SWVersion__":""})

        ## Parse the testrun template
        test_run_details = {**Templates.TESTRUN_DB_TEMPLATE, **Templates.TESTRUN_SUMMARY_TEMPLATE}
        #test_run_details = self.test_run_template  # self.args #TESTRUN_DETAILS_TEMPLATE
        #test_run_details['runid'] = test_run_details['run-tag']
        if '__TESTSUITE_LABEL__' in self.args['custom_params']: test_run_details['suitelabel'] = self.args['custom_params']['__TESTSUITE_LABEL__']
        for tr_fld in test_run_details:
            if tr_fld in self.args: test_run_details[tr_fld] = self.args[tr_fld]
        test_run_details['pid'] = os.getpid()
        test_run_details['server_ip'] = helper.get_server_ip()
        test_run_details['server_port'] = Constants.SERVER_PORT
        test_run_details['report_url'] = 'http://{host}:{port}/browse_dir?path={report_file}'.format(host=test_run_details['server_ip'],
                                                                             port=test_run_details['server_port'],
                                                                             report_file='{}/log.html'.format(
                                                                                 test_run_details['log-path']))
        test_run_details['report_path'] = '{}/log.html'.format(test_run_details['log-path'])
        #if 'runid' not in test_run_details:
        #if 'run-tag' not in args: raise Exception('run-tag in testrun payload is not defined')
        #if not args['run-tag']: raise Exception('run-tag in testrun payload is 0')
        test_run_details['runid'] = self.args['run-tag']
            #test_run_details['runid'] = args['run-tag']
        try:
            test_run_details['runid'] = int(test_run_details['runid'])
        except:
            raise Exception ('runid must be either int or str convertable to int')
        #runid = args['runid']
        if self.logger:
            self.logger.info ("adding test run {}". format(test_run_details['runid']))
        # Add testrun to MongoDB
        #test_run_details = remove_dots_from_keys(test_run_details)
        with Mongo('testruns') as testruns:
            testruns.add_to_db(test_run_details['runid'], test_run_details, check_if_exists=True)

    def delete_legacy_records(self):
        try:
            data_keep_for_days = None
            if not self.args:
                raise Exception("no args defined for 'delete_legacy_records' method")
            if 'custom_params' in self.args:
                if '__KEEP_DATA_DAYS__' in self.args['custom_params']:
                    data_keep_for_days = self.args['custom_params']['__KEEP_DATA_DAYS__']
            if not data_keep_for_days: data_keep_for_days = Constants.KEEP_DATA_DAYS
            clean_up_from_time = datetime.now() - timedelta(days=int(data_keep_for_days))
            myDb = Mongo()
            if not myDb.count_docs({'created_datetime':{'$lt':clean_up_from_time}}, collection='testruns'): return None
            runid_dict = myDb.get_fields({'created_datetime':{'$lt':clean_up_from_time}}, 'runid', collection='testruns', find_one=False)
            run_id_lst = []
            run_id_lst.extend(value for d in runid_dict for value in d.values())
            log_path_dict = myDb.get_fields({'created_datetime': {'$lt': clean_up_from_time}}, 'log-path',
                                         collection='testruns', find_one=False)
            log_path_lst = []
            log_path_lst.extend(value for d in log_path_dict for value in d.values())
            helper.delete_log_dir(log_path_lst)
            selector = {'runid': {'$in': run_id_lst}}
            myDb.delete_db(selector,'kws')
            myDb.delete_db(selector, 'testcases')
            myDb.delete_db(selector, 'testsuites')
            myDb.delete_db(selector, 'testruns')
            myDb.close()
        except Exception as e:
            if myDb:
                myDb.close()
            if self.logger:
                self.logger.error('DB cleanup exception: {} traceback = {}'.format(e, helper.get_traceback()))


    def add_robot_params(self, robot_params):
        if self.logger:
            self.logger.info ("adding robot params to run {}". format(self.args['run-tag']))
        try:
            runid = int(self.args['run-tag'])
        except:
            raise Exception ('runid must be either int or str convertable to int')
        # Add testrun to MongoDB
        with Mongo('testruns') as collection:
            collection.update_db(runid, {'$addToSet':{'test_param':{'robot':robot_params}}})

    def get_taf_robot_params(self):
        log_path = self.args['log-path']
        dry_run_log_path = log_path + '/dry-run'
        os.makedirs(dry_run_log_path, mode=0o777, exist_ok=True)
        #self.args['log-path'] = dry_run_log_path
        inputData, reg_type = helper._get_taf_inputdata(deepcopy(self.args), robot_dryrun=True)
        inputData['outputdir'] = dry_run_log_path
        helper._taf_runner(inputData, reg_type, self.logger)
        if 'CMD_OPTIONS' not in os.environ:
            raise Exception ("regClass regression dry-run failed. 'CMD_OPTIONS' env variable has not been set")
        robot_params = eval(os.environ['CMD_OPTIONS'])
        #robot_params = robot_params[1:]
        #robot_params = ConvertLstToDict(robot_params)
        return robot_params

    def start_taf_run(self):
        inputData, reg_type  = helper._get_taf_inputdata(deepcopy(self.args), robot_dryrun=False)
        self.logger.info("Start TAF run. inputData: {},  reg_type: {}".format(inputData, reg_type))
        helper._taf_runner(inputData, reg_type, self.logger)

class TestRun:
    @staticmethod
    def append_suite_to_list(runid, suite_name, logger=None, db=None):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        if logger:
            logger.info ("runid {}: appending suite {} to the testrun...". format(runid, suite_name))
        # Add testrun to MongoDB
        if db:
            db.update_db(runid, {'$addToSet': {'suites': suite_name}}, collection='testruns')
        else:
            with Mongo('testruns') as testruns:
                testruns.update_db(runid,{'$addToSet':{'suites':suite_name}})


    @staticmethod
    def update_testrun(runid, logger=None, db=None, **kwargs):#status=None):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        if kwargs:
            if logger:
                logger.info ("runid {}: update testrun with {}". format(runid, kwargs))
            # Add testrun to MongoDB
            if db:
                db.update_db(runid, {'$set': kwargs}, collection='testruns')
            else:
                with Mongo('testruns') as testruns:
                    testruns.update_db(runid,{'$set': kwargs})

    @staticmethod
    def update_testrun_is_alive(runid, logger=None, db=None, c_status='FINISHED', interval_sec=120):#status=None):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        if logger:
            logger.info ("runid {}: update testrun is_alive status". format(runid))
        pid_dict = db.get_fields(runid, ['pid','is_alive','is_alive_last_check','status'], collection='testruns')
        if pid_dict:
            pid = pid_dict.get('pid', None)
        else:
            return None, None
        is_alive = pid_dict.get('is_alive', True)
        if pid:
            difference = datetime.now() - pid_dict.get('is_alive_last_check', datetime.now() - timedelta(interval_sec+10))
            if difference.total_seconds() > interval_sec:
                is_alive = helper.is_process_alive(pid)
                #Active run
                if (pid_dict['status'] != c_status and is_alive^pid_dict['is_alive']) or (pid_dict['status'] == c_status and pid_dict['is_alive']):
                    if db:
                            db.update_db(runid, {'$set': {'is_alive': is_alive, 'is_alive_last_check':datetime.now()}}, collection='testruns')
                    else:
                        with Mongo('testruns') as testruns:
                            testruns.update_db(runid, {'$set': {'is_alive': is_alive, 'is_alive_last_check':datetime.now()}})
            return is_alive, pid
        return None, None

    @staticmethod
    def get_list_of_tests (runid, db, logger=None):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        if logger:
            logger.info ("runid {}: get list of tests". format(runid))
        test_lst = []
        suites_dict = db.get_fields(runid, ['suites', 'log-path'], collection='testruns')
        suites_lst = suites_dict['suites']
        max_sqn = 0
        for suite in suites_lst:
            suite_dict = db.get_fields({'runid':runid,'suitename':suite}, ['setup','teardown', 'tests', 'suitemetadata'], collection='testsuites',find_one=True)
            for tp in suite_dict:
                if tp in ['setup','teardown']:
                    if suite_dict[tp]:
                        kw_dict = db.get_fields({'runid':runid,'suite':suite,'kwname':suite_dict[tp]}, ['_id', 'kwname', 'status', 'result', 'kwmetadata', 'sqn'], collection='kws',find_one=True)
                        #['name', 'pathname', 'status', 'sequence', 'sid', 'result', 'message', 'description', 'id', 'starttime', 'endtime']
                        error = ''
                        message = ''
                        if 'message' in suite_dict['suitemetadata']:
                            if suite_dict['suitemetadata']['message']:
                                error = suite_dict['suitemetadata']['message'] if kw_dict['result'] not in ['PASS'] else ''
                                message = suite_dict['suitemetadata']['message']
                        if os.path.exists('{}/log.html'.format(suites_dict['log-path'])):
                            log = '{}/log.html#{}'.format(suites_dict['log-path'], suite_dict['suitemetadata']['id'])
                        else:
                            log = '{}/runinfo.html'.format(suites_dict['log-path'])
                        sequence = kw_dict.get('sqn', None)
                        if sequence is None: sequence = max_sqn
                        if sequence > max_sqn: max_sqn = sequence
                        test_lst.append({'description':kw_dict['kwmetadata']['doc'],
                                         'ended_time': datetime.strptime(kw_dict['kwmetadata']['endtime'],
                                                                         "%Y%m%d %H:%M:%S.%f").strftime(
                                             '%a, %d %b %Y %H:%M:%S GMT') if 'endtime' in kw_dict['kwmetadata'] and kw_dict['status'] in ['STARTED', 'COMPLETE'] else '',
                                         'log': log,
                                         'message': message,
                                         'name':'SUITE ' + tp.upper()+': '+ kw_dict['kwname'],
                                         'pathname':suite+'.'+kw_dict['kwname'],
                                         'result':kw_dict['result'],
                                         'result_color': helper.get_color_status(kw_dict['result']),  # '#66cc66',
                                         'status':kw_dict['status'],
                                         'sequence':sequence,
                                         'started_time': datetime.strptime(kw_dict['kwmetadata']['starttime'],
                                                                           "%Y%m%d %H:%M:%S.%f").strftime(
                                             '%a, %d %b %Y %H:%M:%S GMT') if 'starttime' in kw_dict[
                                             'kwmetadata'] and kw_dict['status'] in ['STARTED', 'COMPLETE'] else '',
                                         'sid': 0,
                                         'status_color': helper.get_color_status(kw_dict['status']),  # '#4775d1',
                                         'subtests': '',
                                         'type':kw_dict['kwmetadata']['type'],
                                         'testcase_id': str(kw_dict['_id']),
                                         'title': suite+'.'+kw_dict['kwname']})
                elif 'tests' in tp:
                    if suite_dict[tp]:
                        for test in suite_dict[tp]:
                            tc_dict = db.get_fields({'runid': runid, 'suite': suite, 'testname':test},  ['testname','longname','status', 'sequence', 'sid', 'result', 'type', 'testmetadata','sqn'], collection='testcases', find_one=True)
                            error = ''
                            message = ''
                            if 'message' in tc_dict['testmetadata']:
                                if tc_dict['testmetadata']['message']:
                                    error = tc_dict['testmetadata']['message'] if tc_dict['result'] not in ['PASS'] else ''
                                    message = tc_dict['testmetadata']['message']
                            if os.path.exists('{}/log.html'.format(suites_dict['log-path'])):
                                log = '{}/log.html#{}'.format(suites_dict['log-path'], tc_dict['testmetadata']['id'])
                            else:
                                log = '{}/runinfo.html'.format(suites_dict['log-path'])
                            sequence = tc_dict.get('sqn', None)
                            if sequence is None: sequence = max_sqn
                            if sequence > max_sqn: max_sqn = sequence
                            ## Append tc metadata to the list
                            test_lst.append({'description':tc_dict['testmetadata']['doc'],
                                         'ended_time':datetime.strptime(tc_dict['testmetadata']['endtime'], "%Y%m%d %H:%M:%S.%f").strftime('%a, %d %b %Y %H:%M:%S GMT') if 'endtime' in tc_dict['testmetadata'] and tc_dict['status'] in ['STARTED', 'COMPLETE'] else '',
                                         'log': log,
                                         'message': message,
                                         'name':tc_dict['testname'],
                                         'pathname':tc_dict['longname'],
                                         'result':tc_dict['result'],
                                         'result_color': helper.get_color_status(tc_dict['result']),  # '#66cc66',
                                         'status': tc_dict['status'],
                                         'sequence': tc_dict.get('sqn', None),
                                         'started_time': datetime.strptime(tc_dict['testmetadata']['starttime'], "%Y%m%d %H:%M:%S.%f").strftime('%a, %d %b %Y %H:%M:%S GMT') if 'starttime' in tc_dict['testmetadata'] and tc_dict['status'] in ['STARTED', 'COMPLETE'] else '',
                                         'sid': 0,
                                         'status_color': helper.get_color_status(tc_dict['status']),  # '#4775d1',
                                         'subtests': '',
                                         'type': tc_dict['type'],
                                         'testcase_id': tc_dict['testmetadata']['id'],  # '63ce6fd5',
                                         'title': tc_dict['longname']})
            #db.update_db(runid, {'$set': kwargs}, collection='testruns')

        return sorted(test_lst, key=lambda d: (d["sequence"] is None, d["sequence"]))

    @staticmethod
    def call_back_complete(runid, logger=None, complete=True):
        try:
            runid = int(runid)
        except:
            raise Exception ('runid must be either int or str convertable to int')
        try:
            #myDb = Mongo()
            with Mongo('testruns') as testruns:
            ### get testrun pid and status ###
                call_back_dict = testruns.get_fields(runid, ['call_back_url','server_ip','server_port'])

            call_back_url = '' if call_back_dict is None else call_back_dict['call_back_url']
            if not complete:
                call_back_url = call_back_url.replace('complete','update')
                call_back_api = 'get_testrun_satatus'
            else:
                call_back_api = 'get_testrun_summary'
            if call_back_url:
                server_ip = call_back_dict['server_ip']
                port_num = call_back_dict['server_port']
                response = helper.get("http://{}:{}/{}".format(server_ip, port_num, call_back_api), runid)
                # call_back_status = helper.post(call_back_url, response.json())
                data = response.json()
                data['test_agent'] = "http://{}:{}".format(server_ip, port_num)
                if logger:
                    logger.info("{} calling back to {}".format(runid, call_back_url))
                call_back_status = helper.post(call_back_url, data=data)#json.dumps(data))
                status_code = call_back_status.status_code
                if logger:
                    logger.info("{} call back status: {} {}".format(runid, call_back_status, status_code))
                #db.update_testrun_callback_status(runid, status_code)
                #myDb.update_db(runid, {'$set': {'is_alive': run_status['is_alive']}}, collection='testruns')

            #myDb.close()
        except Exception as error:
            if logger:
                logger.error("{} call back error: {}".format(runid, error))
            else:
                print ("{} call back error: {}".format(runid, error))

    @staticmethod
    def call_back_update(runid, logger=None):
        TestRun.call_back_complete(runid, logger=logger, complete=False)
