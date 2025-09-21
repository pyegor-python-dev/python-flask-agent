__author__ = "Yegor Parfenov"
BASE_PATH = "/home/automation"#"/Users/yparfenov/PycharmProjects"#
#from asyncio.subprocess import Process
from multiprocessing import Process
#from Testscripts.EmbeddedQA.IBP.InlineSSL.rename import target
### System module imports ###
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from flask import Flask, make_response, send_file, send_from_directory, request, jsonify, Response
#from flask_restplus import Resource, Api, fields
from flask_restx import Resource, Api, fields
from flask_autoindex import AutoIndex
import os, sys
import signal
import git
from datetime import datetime
import psutil
from threading import Thread
import time
from glob import glob

app = Flask(__name__)
rootdir = AutoIndex(app, browse_root='/', add_url_rules=False)
api = Api(app, version='0.1', title='Gigatest API', description='REST API to perform gigatest operations')


#from pymongo import MongoClient
#qq = os.path.dirname (os.path.realpath(__file__))
#BASE_PATH = Constants.BASE_PATH #constants.os.path.dirname (os.path.realpath(__file__))
sys.path.append (BASE_PATH)#(os.path.dirname (BASE_PATH))

from Gigatest.lib import gutils
from Gigatest.lib.constants import Constants as Constants


gutils.add_sys_path ('{}/Gigatest'.format (BASE_PATH),
                     '{}/Gigatest/lib'.format (BASE_PATH),
                     '{}/fm_auto_test'.format(BASE_PATH),
                     '{}/fm_auto_test/lib'.format(BASE_PATH),
                     '{}/Userlib'.format(BASE_PATH),
                     '{}/Gigascripts'.format(BASE_PATH)) #'{}/Gigatest/lib/py'.format (BASE_PATH), '{}/Userlib'.format(BASE_PATH), '{}/Gigascripts'.format(BASE_PATH)
#utils.add_sys_path (BASE_PATH, '{}/lib'.format (BASE_PATH), '{}/lib/py'.format (BASE_PATH), '{}/fm_auto_test/lib'.format(os.path.dirname(BASE_PATH)))
### Gigtest lib imports ###
from Gigatest.lib.templates import Templates
from Gigatest.lib import gutils
from Gigatest.lib import cmd_util
from Gigatest.lib.helper import HelperMethods as helper

#from Gigatest.lib.gigalogger import GLog, Log
from Gigatest.lib.helper import Mongo
from Gigatest.lib.testrunner import TestRunner, TestRun #, StartTestRunProcess
from Gigatest.lib.testsuite import TestSuite
from Gigatest.lib.testsuite import TestCase

#global server_ip

# get server ip
#print("getting server IP")
#server_ip =

#requests.packserver_ipages.urllib3.disable_warnings(InsecureRequestWarning)






#utils.add_sys_path ("/".join(os.getcwd().split("/")[0:-1]))

#BASE_PATH = os.path.dirname (os.path.realpath(__file__))
#sys.path.append (os.path.dirname (BASE_PATH))
#gutils.add_sys_path (BASE_PATH, '{}/lib'.format (BASE_PATH), '{}/lib/py'.format (BASE_PATH))

def on_terminate(proc):
    print(("***process {} terminated with exit code {}".format(proc, proc.returncode)))

def terminate_run(pid, timeout=20):
    #print ("***terminating processed with SIGTERM...")
    #kill_proc_tree(pid, signal.SIGTERM, include_parent=True, timeout=10, on_terminate=on_terminate)
    print ("***killing processed that are still alive with SIGKILL...")
    return kill_proc_tree(pid, signal.SIGKILL, include_parent=True, timeout=timeout, on_terminate=on_terminate)


def kill_proc_tree(pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    children.reverse()
    if include_parent:
        children.append(parent)
    for p in children:
        print(("terminating {} using {}...".format(p.pid, sig)))
        try:
            p.send_signal(sig)
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(children, timeout=timeout,
                                    callback=on_terminate)
    return (gone, alive)

class Model(object):
    '''
    Description: Class to model the schema of the a test run request
    '''
    test_run = api.model('test', {
        'test_file': fields.String(required=False, description="Name of the test file that will be executed"),
        'testsuite': fields.String(required=False, description="Name of the test suite file that will be executed. "
                                                               "It's required if xml blob is not passed"),
        'test_param': fields.List(required=False, cls_or_instance=fields.String, description="Name of the test parameter file that will be used. "
                                                              "It's required if xml blob is not passed"),
        'xml': fields.String(required=False, description="XML doc to descript the test run.  It's rquired if test_file "
                                                         "and test_param are not passed"),
        'debug': fields.Boolean(required=False, default=True, description="Enable verbal output to stdout as well as in the logs"),
        'timeout': fields.Integer(required=False, description="Timeout value for the testcase exections"),
        'log-path': fields.String(required=False, description="Testase log path"),
        'testname': fields.String(required=False, description="Test case name, and it's required when runing python tests"),
        'testrail_run': fields.String(required=False, description="Testrail run name"),
        'testrail_id': fields.String(required=False, description="Testrail id"),
        'testrail_plan': fields.String(required=False, description="Testrail plan name"),
        'build': fields.String(required=False, description="Build number"),
        'swversion': fields.String(required=False, description="SW Version"),
        'email': fields.String(required=False, description="email address"),
        'run-tag': fields.String(required=False, description="test run identification"),
        'branch': fields.String(required=False, description="Branch name"),
        'model': fields.String(required=False, description="Model name"),
        'build_url': fields.String(required=False, description="Build url"),
        'resource': fields.String(required=False, description="Resource name"),
        'review_number': fields.String(required=False, description="Review number"),
        'committer': fields.String(required=False, description="Committer"),
        'call_back_url': fields.String(required=False, description="URL that will be called back for result notification"),
        'jenkins_job_url': fields.String(required=False, description="Jenkins Job URL"),
    })
    test_stop = api.model('test_stop', {
        'runid': fields.String(required=True, description="The ID of the test run")
    })
    test_run_details = api.model('test_run_model', {
        'is_alive':fields.Boolean,
        'runid': fields.String,
        'suitename': fields.String,
        'suitelabel': fields.String,
        'status': fields.String,
        'pid': fields.String,
        'testcases': fields.List(cls_or_instance=fields.String),#(attribute='name')),
        'updated_datetime': fields.String, #DateTime(dt_format='rfc822'),
        'created_datetime': fields.String, #DateTime(dt_format='rfc822')
    })
    test_run_summary = api.model('test_run_summary_model', {
        'runid': fields.String,
        'suitename': fields.String,
        'suitelabel': fields.String,
        'status': fields.String,
        'testcases': fields.List(cls_or_instance=fields.Nested({'name': fields.String, 'status': fields.String,
                                                'result': fields.String})),
        'num_of_testcases': fields.Integer,
        'num_of_pass': fields.Integer,
        'num_of_fail': fields.Integer,
        'num_of_skip': fields.Integer,
        'num_of_unknown': fields.Integer,
        'num_of_completed': fields.Integer
    })
    testcase_details = api.model('testcase_model', {
        'runid': fields.String,
        'name': fields.String,
        'sequence': fields.Integer,
        'sid': fields.Integer,
        'type': fields.String,
        'log_file': fields.String,
        #'argString': fields.String,
        'status': fields.String,
        'result': fields.String,
        'logs': fields.List(cls_or_instance=fields.String),
        'updated_datetime': fields.String, #fields.DateTime(dt_format='rfc822'),
        'created_datetime': fields.String#fields.DateTime(dt_format='rfc822')
    })

    test_run_status = api.model('test_run_status', {
        'run_id': fields.String(required=True, description="The ID of the test run")
    })

    test_case_logs = api.model('test_run_logs', {
        'run_id': fields.String(required=True, description="The ID of the test run"),
        'testcase_name': fields.String(required=True, description="The name of the test case")
    })




@api.route('/start_run')
class StartRun(Resource):
    @api.expect(Model.test_run)
    @api.response(201, Constants.OK)
    @api.response(400, Constants.FAILED)
    def post(self):
        '''
        Description: Post method to provie starting of a test run
        '''
        print('start a new test run')
        log_path = api.payload ['log-path'] if 'log-path' in api.payload else None
        #log_path = '/mnt/automation/GigatestLogs/release/UCT_61100/529646/8903770'
        if log_path:
            cmd_util.makedirs(log_path)
        else:
            raise Exception("Log path is not defined in payload")

        #logger = helper.get_logger(log_path,'runner.log')
        try:
            arguments = helper.parse_args(api.payload)
            #arguments = {'branch': 'release/UCT_61100', 'build': 529646, 'build_url': None, 'call_back_url': 'https://gigaq.gigamon.com:443/job/complete/', 'committer': 'yegor.parfenov', 'custom_params': {'__EXCLUDE_TAG__': 'NOTcloud_feature_uct_Policy_stats_copy11', '__FMVersion__': '6.10.00', '__INCLUDE_TAG__': 'cloud_feature_uct_Policy_stats_copy11', '__MAX_RUN_TIME__': 172800, '__SOLUTION__': 'UCT', '__TESTSUITE_LABEL__': 'fm_cloud_uctc_pre_test'}, 'email': 'yegor.parfenov@gigamon.com', 'jenkins_job_url': '', 'library_path': '/home/automation/fm_auto_test/lib:/home/automation/Userlib:/home/automation/fm_test_scripts:/home/automation/fm_auto_test/tools:/home/automation/Gigatest:/home/automation', 'log-path': '/mnt/automation/GigatestLogs/release/UCT_61100/529646/8903770', 'model': 'uct', 'resource': 'UCT-PRE-TEST-Resource-Pool', 'review_number': 'GIGAQ', 'run-tag': '8903770', 'run_timeout': 86400, 'started_by': 'yegor.parfenov', 'test_param': [{'data': {'autosplit': 'False', 'cloudPlatforms': ['vmwareEsxi'], 'collectLogs': 'True', 'emailPrefix': 'cloud_feature_uct_redesign', 'exclude': ['NOTcloud_feature_uct_Policy_stats_copy11'], 'fmVersion': ['BUILD_VERSION'], 'include': ['cloud_feature_uct_Policy_stats_copy11'], 'mailTo': ['duvvarapu.nagamani@gigamon.com', 'sridhar.genji@gigamon.com', 'balamurugan.gopal@gigamon.com', 'gunasekaran.mohan@gigamon.com'], 'regList': ['cloud_functional'], 'request': 'developerReg', 'skipRepoUpdate': 'True', 'splitlog': 'False', 'suites': ['cloud_functional'], 'variables': {'BUILD_INFO': {'uct': {...}}, 'DESTROY': 'False', 'DEV_VERSION': 'BUILD_VERSION', 'DO_NOTHING_TO_DEVICE': 'False', 'IPType': 'lab', 'JACOCOENABLED': 'False', 'JSON_EXTN': 'esxi_testbed_ipv4', 'PLATFORM': 'vmwareEsxi', 'POST_RESULT': '1', 'PRE_CLEANUP': 'True', 'REG_TYPE': 'standardReg', 'REUSE': 'False', 'SELF_REG': 'True', 'TESTBED': 'esxi_uct_ci_cd', 'UCTC_VERSION': 'BUILD_VERSION', 'VSERIES_VERSION': 'BUILD_VERSION'}}}, {'envar': {'HOME': '/home/automation', 'PYTHONPATH': '/home/automation/fm_auto_test/lib:/home/automation/Userlib:/home/automation:/home/automation/FM_Ansible/integration:/usr/local/share/gigamon/module_utils:/home/automation/Gigascripts/:/home/automation/Gigatest/:/home/automation/Userlib/SharedLib:/home/automation/fm_auto_test/lib/robot_keywords', 'TAF_HOME': '/home/automation/fm_auto_test'}}], 'test_type': 'robot', 'testbed': 'FM-UCT-CLOUD-PRE-TB2', 'testsuite': '/home/automation/fm_auto_test/tools/runReg'}
            if 'test_type' not in arguments: arguments['test_type'] = 'robot'

            p = TestRunner(arguments, log_path)
            p.start()
            #prc.join()
            #### For TAF suites, perform a dry-run to get a list of Robot arguments out of the payload params
            #TestRunner.start(arguments, logger)
            return {"run-tag": arguments['run-tag'], "log_id": arguments['run-tag']}, 201


        except Exception as e:
            print ("failed to start test run, encountered exception: {} {}".format(e, helper.get_traceback ()))
            return {"Status": "failed to start test run because of exception: {} traceback={}".format(e,helper.get_traceback())}, 400

@api.route('/get_testrun_status/<string:runid>')
class GetTestRunStatus(Resource):
    #@api.expect(Model.test_run_status)
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid):
        '''
        Description: Get testrun status
        '''
        run_status = {
            'is_alive': None,
            'num_of_completed': 0,
            'num_of_fail': 0,
            'num_of_in_progress': 0,
            'num_of_pass': 0,
            'num_of_skip': 0,
            'num_of_testcases': 0,
            'num_of_unknown': 0,
            'pid': None,
            'started_by': '',
            'status': None,
        }

        print("get testrun status for id: {}".format(runid))
        runid = int(runid)
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)
            tr_dict = myDb.get_fields(runid, ['status','started_by','is_alive','pid'], collection='testruns')
            run_status['started_by'] = '' if tr_dict is None else tr_dict['started_by']
            run_status['status'] = None if tr_dict is None else tr_dict['status']
            run_status['is_alive'] = None if tr_dict is None else tr_dict['is_alive']
            run_status['pid'] = None if tr_dict is None else tr_dict['pid']
            if run_status['status'] is None or run_status['status'] not in Templates.TESTRUN_STATUS:
                run_status['status'] = 'UNKNOWN'
                resp = jsonify(run_status)
                helper.set_no_cache(resp)
                resp.status_code = 200
                return resp
            run_status.update(TestCase.get_testcase_stats(runid, myDb))
            myDb.close()

            ####### return status back to requestor ############
            resp = jsonify(run_status)
            helper.set_no_cache(resp)
            resp.status_code = 200
            return resp
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get testrun status, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get testrun status because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

# endpoint to get testrun details
@api.route('/get_testrun_detail/<string:runid>')
class GetTestRunDetail(Resource):
    #@api.expect(Model.test_run_status)
    @api.marshal_with(Model.test_run_details, envelope='testrun_details')
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)

# Response:
# {
#   "testrun_details": {
#     "runid": "7679530",
#     "suitename": "/home/automation/fm_auto_test/tools/runReg",
#     "suitelabel": "Gen3_Gigasmart_pre",
#     "status": "STARTED",
#     "pid": "2527457",
#     "testcases": [
#       "Dedup with action as drop duplicate with dedup timer as 5000",
#       "DSSL with DSSL_SSL_3DESCBCSHA",
#       "DSSL with TLS11_DES_CBC3_SHA_key2k_selfsigned",
#       "DSSL with TLS12AES256_SHA256_k4k",
#       "Check Masking functionality with protocol ipv4 with offset 1",
#       "Check Slicing functionality with protocol tcp and offset 127",
#       "Verify encap functionality with key as 0",
#       "To Verify APF for gsrule vlan any range filters the matching packets",
#       "Verify BASF Session Creation and Filtering: Session Field: 5tuple",
#       "C25570675 C25570676 C25570677 Map Rule Edit: Verify flowsample rule insert before / rule insert after / Delete rule with higher priority",
#       "To verify App metadata-AMI with GTP_IpFix_withstats",
#       "To verify App metadata-AMI with dns1_and_dns2_CEF_withstats",
#       "Verify the behavior of Outbound Flex Inline SSL with decrypt list.",
#       "Verify the behavior of Outbound Flex Inline SSL with no_decrypt list.",
#       "Verify the behavior of Inbound Flex Inline SSL with decrypt list.",
#       "Verify the behavior of Inbound Flex Inline SSL with no_decrypt list.",
#       "Verify VLAN header is stripped correctly for packets: next header IPv4",
#       "Verify enhanced slicing with protcol as gtp",
#       "Verify AFI with protocol sctp for app diameter"
#     ],
#     "updated_datetime": "Thu, 02 May 2024 13:47:39 -0000",
#     "created_datetime": "Thu, 02 May 2024 12:42:04 -0000"
#   }
# }

    def get(self, runid):
        '''
        Description: Get testrun details
        '''

        run_detail = {
            "is_alive":True,
            "created_datetime": "",  # "Fri, 21 Jun 2024 12:56:49 -0000"
            "runid": runid,
            "suitename": "", #"/home/automation/fm_auto_test/tools/runReg",
            "suitelabel": "", #"fm_vseries_esxi_post",
            "status": None, #"STARTED",
            "pid": None, #"1340473",
            "testcases": [],
            "updated_datetime": "", #"Fri, 21 Jun 2024 14:14:16 -0000",
        }
        runid = int(runid)
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)

            ###################################

            tr_dict = myDb.get_fields(runid, ['pid','is_alive','testsuite','suitelabel','status','created_datetime','updated_datetime'], collection='testruns')
            run_detail['suitename'] = '' if tr_dict is None else tr_dict['testsuite']
            run_detail['suitelabel'] = '' if tr_dict is None else tr_dict['suitelabel']
            run_detail['created_datetime'] = '' if tr_dict is None else tr_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            run_detail['updated_datetime'] = '' if tr_dict is None else tr_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            run_detail['status'] = None if tr_dict is None else tr_dict['status']
            run_detail['pid'] = None if tr_dict is None else tr_dict['pid']
            run_detail['is_alive'] = True if tr_dict is None else tr_dict['is_alive']
            if run_detail['status'] is None or run_detail['status'] not in Templates.TESTRUN_STATUS:
                run_detail['status'] = 'UNKNOWN'
                #resp = jsonify(run_detail)
                #helper.set_no_cache(resp)
                #resp.status_code = 200
                return run_detail, 200
            tc_dict = TestRun.get_list_of_tests(runid, myDb) #myDb.get_fields(runid, 'longname', collection='testcases', find_one=False)
            #run_detail.update(TestCase.get_testcase_stats(runid, myDb))
            tc_title_dict = [{"title": d["title"]} for d in tc_dict]
            run_detail['testcases'].extend(value for d in tc_title_dict for value in d.values())
            myDb.close()
            #resp = jsonify(run_detail)
            #helper.set_no_cache(resp)
            #resp.status_code = 200
            return run_detail, 200
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get test run details, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get testrun details because of exception: {} traceback={}'.format(e, helper.get_traceback ())})
            resp.status_code = 400
            return resp

# endpoint to stop a test run
@api.route('/stop')
class stop(Resource):
    @api.expect(Model.test_stop)
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def post(self):
        '''
        Description: Get testrun status
        '''
        try:
            print('Stopping a test run')
            print(('request payload: {}'.format(api.payload)))
            #myDb = Mongo()
            runid = api.payload["runid"]
            runid = int(runid)
            # run_detail = {
            #     "runid": runid,
            #     "suitename": "",  # "/home/automation/fm_auto_test/tools/runReg",
            #     "suitelabel": "",  # "fm_vseries_esxi_post",
            #     "status": None,  # "STARTED",
            #     "pid": None,  # "1340473",
            #     "testcases": [],
            #     #     "Validate Vseries DHCP IP Node deployment with Small-Medium and Thin",
            #     #     "Validate Vseries Node Static Ip deployment with Medium-Large and Thick",
            #     #     "Validate Two Vseries Static IP Node deployment with Small and Shared Storage",
            #     #     "Validate VM Folder and Local Storage"
            #     # ],
            #     "updated_datetime": "",  # "Fri, 21 Jun 2024 14:14:16 -0000",
            #     "created_datetime": ""  # "Fri, 21 Jun 2024 12:56:49 -0000"
            # }

            myDb = Mongo()
            ### get testrun pid and status ###
            pid_dict = myDb.get_fields(runid, 'pid', collection='testruns')
            pid = None if pid_dict is None else pid_dict['pid']
            is_alive = True
            time.sleep(1)
            if pid:
                is_alive = helper.is_process_alive(pid)
                #myDb.update_db(runid, {'$set': {'is_alive': is_alive}}, collection='testruns')

            ###################################

            if pid and is_alive:

                print(("kill process {} associated with runid {}".format(pid, runid)))
                #jobs[api.payload['runid']][0].terminate()
                #os.system('kill ' + str(pid_run))
                kthread = Thread(target=terminate_run, args=( pid,  20))
                kthread.start()
                kthread.join(10)
                #myDb.update_testrun_status(runid, "ABORTED")

            myDb.update_db(runid, {'$set': {'status': 'ABORTED','ended_time':datetime.now()}}, collection='testruns') #myDb.update_testrun_status(runid, "ABORTED")
            myDb.close()
            resp = jsonify({'status': 'successful'})
            resp.status_code = 200
            return resp
        except Exception as e:
            if myDb: myDb.close()
            print(("failed to kill process {} associated with runid {} due to error: {}".format(pid, runid, e)))
            resp = jsonify({'status': 'failed to stop testrun because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

# endpoint to get testrun details
@api.route('/get_testrun_summary/<string:runid>')
class GetTestRunSummary(Resource):
    #@api.marshal_with(Model.test_run_summary, envelope='testrun_summary')
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid):
        '''
        Description: Get testrun summary
        '''
        summary = {
            'elapsed_time': None,
            'error_message': None,
            'runid': runid,
            'suitename': None,
            'suitelabel': None,
            'status': None,
            'started_time': None,
            'updated_time': None,
            'run_timeout': 0,
            'testcases': [],
            'num_of_testcases': 0,
            'num_of_unknown': 0,
            'num_of_pass': 0,
            'num_of_fail': 0,
            'num_of_skip': 0,
            'num_of_in_progress': 0,
            'num_of_completed': 0,
            'started_by': None,
            'pid': None,
            'is_alive': None,
            'report_path': None,
            'report_url': None
        }
        # testcase = {
        #     'description': '',
        #     'ended_time': None,
        #     'error': '',
        #     'log': '', #'/mnt/automation/GigatestLogs/master/462474/7880760/runReg.125650/log.html',
        #     'message': '',
        #     'name': '', #'Validate Vseries DHCP IP Node deployment with Small-Medium and Thin',
        #     'pathname': '', #'Validate Vseries DHCP IP Node deployment with Small-Medium and Thin',
        #     'result': '',
        #     'result_color': '', #'#66cc66',
        #     'sequence': 0,
        #     'sid': 0,
        #     'started_time': '', #'Fri, 21 Jun 2024 13:26:20 GMT',
        #     'status': '', #'COMPLETE',
        #     'status_color': '', #'#4775d1',
        #     'subtests': '',
        #     'testcase_id': None, #'63ce6fd5',
        #     'title': '', #'Cloud Functional.Hybrid.6.3.00.vmwareEsxi.Sanity.Testcases',
        #     'type': 'Robot'
        #     }
        runid = int(runid)
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)

            ###################################
            fields = ['testsuite',
                      'suitelabel',
                      'status',
                      'started_by',
                      'started_time',
                      'ended_time',
                      'created_datetime',
                      'updated_datetime',
                      'run_timeout',
                      'report_path',
                      'report_url',
                      'elapsed_time',
                      'error_message',
                      'pid',
                      'is_alive',
                      'log-path']
            tr_dict = myDb.get_fields(runid, fields, collection='testruns')
            if not tr_dict: return summary, 200
            summary['suitename'] = '' if not tr_dict['testsuite'] else tr_dict['testsuite']
            summary['suitelabel'] = '' if not tr_dict['suitelabel'] else tr_dict['suitelabel']
            summary['started_time'] = '' if not tr_dict['created_datetime'] else tr_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            summary['updated_time'] = '' if not tr_dict['updated_datetime'] else tr_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            summary['run_timeout'] = tr_dict['run_timeout']
            summary['started_by'] = tr_dict['started_by']
            summary['status'] =  tr_dict['status']
            summary['report_path'] =  tr_dict['report_path']
            summary['report_url'] =  tr_dict['report_url']
            summary['pid'] =  tr_dict['pid']
            summary['is_alive'] =  tr_dict['is_alive']
            if not summary['status'] or summary['status'] not in Templates.TESTRUN_STATUS:
                summary['status'] = 'UNKNOWN'
                resp = jsonify(summary)
                helper.set_no_cache(resp)
                resp.status_code = 200
                return resp
            if tr_dict['ended_time'] and tr_dict['created_datetime']:
                summary['elapsed_time'] = str(tr_dict['ended_time'] - tr_dict['created_datetime']).split(".")[0]
            else:
                summary['elapsed_time'] = str(datetime.now() - tr_dict['created_datetime']).split(".")[0]
            summary['error_message'] = None if tr_dict is None else tr_dict['error_message']
            summary['testcases'] = TestRun.get_list_of_tests(runid, myDb)
            #summary['testcases'].extend(value for d in tc_dict for value in d.values())
            summary.update(TestCase.get_testcase_stats(runid, myDb))
            myDb.close()
            resp = jsonify(summary)
            helper.set_no_cache(resp)
            resp.status_code = 200
            return resp
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get run summary, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get run summary because of exception: {} traceback={}'.format(e, helper.get_traceback ())})
            resp.status_code = 400
            return resp

# endpoint to get testrun details
@api.route('/get_testrun_junit/<string:runid>')
class GetTestRunJUnit(Resource):
    #@api.marshal_with(Model.test_run_summary, envelope='testrun_summary')
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid):
        '''
        Description: Get testrun status
        '''


        try:
            tr_fields=[
                'created_datetime',
                'log-path',
                'pid',
                #'is_alive,'
                'report_path',
                'report_url',
                'status',
                'server_ip',
                'server_port',
                'started_by',
                'started_time',
                'suitelabel',
                'updated_datetime'
            ]
            tc_fields = [
                'created_datetime',
                'result',
                'status',
                'sequence',
                'sid',
                'testname',
                'type',
                'testmetadata',
                'updated_datetime'
            ]
            runid = int(runid)
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)
            tr = myDb.get_fields(runid, tr_fields, collection='testruns')
            suitename = tr['suitelabel']
            tc_lst = myDb.get_fields(runid, tc_fields, collection='testcases', find_one=False)
            #for tc_dict in tc_lst:
            #    testcase['description'] = tc_dict['testmetadata']['doc']
            #    testcase['ended_time'] = tc_dict['testmetadata']['endtime']
            #myDb.close()
            for tc in tc_lst:
                tc['log'] = 'http://{host}:{port}/browse_dir?path={log_file}'.format(host=tr['server_ip'],port=tr['server_port'], log_file='{}/log.html#{}'.format(tr['log-path'],tc['testmetadata']['id']))

            testcases_xml = self.to_testcases_xml (tc_lst, suitename)

            total = 0
            passes = 0
            errors = 0
            failures = 0
            skips = 0

            passes += testcases_xml ['passes']
            errors += testcases_xml ['errors']
            failures += testcases_xml ['failures']
            skips += testcases_xml ['skipped']
            total += testcases_xml ['total']
            report_path = tr['report_path']

            testsuite = '''
                      <testsuite name="{name}" tests="{tests}"
                          time="{time}" errors="{errors}" failures="{failures}" id="{runid}" >'''.format (name=suitename,
                              tests=testcases_xml['total'], errors=testcases_xml['errors'], failures=testcases_xml['failures'],
                              runid=runid,
                              time=str (tr['updated_datetime'] - tr['created_datetime']).split(".")[0])
            testsuite += '''
                            <properties>
                                 <property name="started_by" value="{started_by}"/>
                                 <property name="started_time" value="{started_time}"/>
                                 <property name="report_path" value="{report_path}"/>
                                 <property name="report_url" value="{report_url}"/>
                                 <property name="suitename" value="{suitename}"/>
                                 <property name="status" value="{status}"/>
                                 <property name="error_message" value="{error_message}"/>
                            </properties>{testcases_xml}'''.format (
                                       started_by=tr['started_by'],
                                       started_time=tr['started_time'],
                                       report_path=tr['report_path'],
                                       report_url=tr['report_url'],
                                       suitename=suitename,
                                       status=tr['status'],
                                       error_message=tr['error_message'] if 'error_message' in tr else '',
                                       testcases_xml=testcases_xml ['xml'])

            testsuite += '</testsuite>'
            testsuites = '''<testsuites tests="{tests}" errors="{errors}" failures="{failures}">{testsuite}
                            </testsuites>'''.format (tests=total, errors=errors, failures=failures, testsuite=testsuite)


            resp = jsonify ({'passes': passes, 'errors': errors, 'failures': failures,
                            'skipped': skips, 'xml': testsuites, 'report_path': report_path})
            helper.set_no_cache(resp)
            resp.status_code = 200
            myDb.close()
            return resp
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get test run junit, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get testrun junit because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

    def _to_testcase_xml_ (self, classname, name, **kwargs):
            classname = self.escape (classname)
            name = self.escape (name)
            result = self.escape (kwargs ['result']).lower() if 'result' in kwargs and kwargs ['result'] else ''
            status = self.escape (kwargs ['status']) if 'status' in kwargs and kwargs ['status'] else ''
            elapsed_time = self.escape (kwargs ['elapsed_time']) if 'elapsed_time' in kwargs and kwargs ['elapsed_time'] else ''
            message = self.escape (kwargs ['message']) if 'message' in kwargs and kwargs ['message'] else ''
            error = self.escape (kwargs ['error']) if 'error' in kwargs and kwargs ['error'] else ''
            assertions = self.escape (kwargs ['title']) if 'title' in kwargs and kwargs ['title'] else ''
            description = self.escape (kwargs ['description']) if 'description' in kwargs and kwargs ['description'] else ''
            log_file = self.escape (kwargs ['log_file']) if 'log_file' in kwargs and kwargs ['log_file'] else ''

            testcase = '''
                      <testcase name="{name}" classname="{classname}" status="{status}"
                           time="{elapsed_time}" assertions="{assertions}">'''.format (name=name,
                                   classname=classname, status=status, elapsed_time=elapsed_time,
                               assertions=assertions)
            if result.startswith('skip'):
                status = 'skipped'
                testcase += '''
                          <skipped>{message}</skipped>'''.format (message=self.escape (message))
            elif result.startswith('error'):
                status = 'errors'
                testcase += '''
                          <error>{message}</error>'''.format (message=self.escape (message))
            elif result.startswith('pass'):
                status = 'passes'
            else:
                status = 'failures'
                testcase += '''
                          <failure>{message}</failure>'''.format (message=self.escape (message))

            testcase += '''
                          <system-out>{log_file}</system-out>
                          <system-err>{error}</system-err>'''.format (
                               log_file=log_file, description=self.escape (description), error=self.escape (error))
                          #<system-out>{description}</system-out>
            return (status, testcase + '</testcase>')

    def to_testcases_xml (self, testcases, classname):
        ret = {'total': 0, 'passes': 0, 'errors': 0, 'failures': 0, 'skipped': 0, 'xml': ''}
        passes = 0
        failures = 0
        errors = 0
        skips = 0
        total = 0
        for tc in testcases:
            ret ['total'] += 1
            status, xml = self._to_testcase_xml_ (classname, tc['testname'], result=tc['result'], status=tc['status'],
                elapsed_time=tc['updated_datetime'], message=self.escape (tc['testmetadata']['message']),
                error=tc['testmetadata']['message'] if tc['result'] not in ['PASS'] else '',
                assertions=tc['title'] if 'title' in tc else '',
                description=tc['testmetadata']['doc'],
                log_file=tc['log'])
            ret [status] += 1
            ret ['xml'] += xml

        return ret

    def escape (self, s):
        try:
            return s.replace ('&', '&amp;').replace ('<', '&lt;').replace ('>', '&gt;').replace ('"', '&quot;').replace ("'", '&apos;')
        except:
            return s

# endpoint to get testrun status
@api.route('/get_testruns_by_status/<string:status>')
class GetTestRunByStatus(Resource):
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, status):
        '''
        Description: Get testruns by status
        '''
        #runid = int(runid)

        fields = [
            'created_datetime',
            'elapsed_time',
            'error_message',
            'is_alive',
            'pid',
            'runid',
            'report_path',
            'started_by',
            'status',
            'testsuite',
            'suitelabel',
            'testbed',
            'updated_datetime',
        ]
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            resp = []
            criteria = {k: v[0] if type(v) in [list, tuple] and len(v) == 1 else v for k, v in
                        list(request.args.to_dict(flat=False).items())}
            #criteria = {k: int(v) if "{}".format(v).isdigit() else v for k, v in list(criteria.items())}
            #c_is_alive = None
            search_criteria = {'status': status}
            if 'is_alive' in criteria:
                c = criteria['is_alive'].lower()
                c_is_alive = True if c == 'true' else False if c == 'false' else None
                if c_is_alive is not None:
                    search_criteria.update({'is_alive':c_is_alive})

            tr_lst = myDb.get_fields(search_criteria, fields, collection='testruns',find_one=False)
            if not tr_lst:
                search_criteria['status'] = 'READY'
                tr_lst = myDb.get_fields(search_criteria, fields, collection='testruns', find_one=False)
            #pid_dict = myDb.get_fields(runid, 'pid',collection='testruns')
            if not tr_lst: return resp
            for tr_dict in tr_lst:
                summary = {
                    'created_datetime': None,
                    'data': '{}',
                    'data_type': 'dict',
                    'elapsed_time': None,
                    'error_message': None,
                    'is_alive': False,
                    'num_of_testcases': None,
                    'num_of_unknown': 0,
                    'num_of_pass': 0,
                    'num_of_fail': 0,
                    'num_of_skip': 0,
                    'pid': None,
                    'report_path': None,
                    'runid':None,
                    'started_by': None,
                    'status': None,
                    'suitename': None,
                    'suitelabel': None,
                    'test_bed': None,
                    'updated_datetime': None,
                    # 'started_time': None,
                    # 'updated_time': None,
                    # 'run_timeout': 0,
                    # 'testcases': [],
                    # 'report_path': None,
                    # 'report_url': None
                }
                if tr_dict:
                    summary['is_alive'] = tr_dict['is_alive']
                    if summary['is_alive']:
                        summary['pid'] = tr_dict['pid']
                    summary['runid'] = str(tr_dict['runid'])
                    summary['created_datetime'] = '' if not tr_dict['created_datetime'] else tr_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
                    summary['elapsed_time'] = tr_dict['elapsed_time']
                    summary['error_message'] =  tr_dict['error_message']
                    #summary['started_time'] = '' if tr_dict is None else tr_dict['started_time']

                    #summary['run_timeout'] = None if tr_dict is None else tr_dict['run_timeout']
                    summary['report_path'] = tr_dict['report_path']
                    summary['started_by'] = tr_dict['started_by']
                    summary['status'] = tr_dict['status']
                    if summary['status'] == 'READY': summary['status'] = 'STARTED'
                    if summary['status'] is None or summary['status'] not in Templates.TESTRUN_STATUS:
                        summary['status'] = 'UNKNOWN'
                    summary['suitename'] = tr_dict['testsuite']
                    summary['suitelabel'] = tr_dict['suitelabel']
                    summary['test_bed'] = tr_dict['testbed']
                    summary['updated_datetime'] = '' if not tr_dict['updated_datetime'] else tr_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
                    summary.update(TestCase.get_testcase_stats(int(summary['runid']), myDb))
                resp.append(summary)
            myDb.close()
            return resp, 200
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get run by status, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get run by status because of exception: {} traceback={}'.format(e, helper.get_traceback ())})
            resp.status_code = 400
            return resp

@api.route('/get_is_alive_testruns/<string:is_alive>')
class GetIsAliveTestRuns(Resource):
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, is_alive):
        '''
        Description: Get alive testruns
        '''
        #runid = int(runid)

        fields = [
            'created_datetime',
            'elapsed_time',
            'error_message',
            'is_alive',
            'pid',
            'runid',
            'report_path',
            'started_by',
            'status',
            'testsuite',
            'suitelabel',
            'testbed',
            'updated_datetime',
        ]
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            resp = []
            #criteria = {k: v[0] if type(v) in [list, tuple] and len(v) == 1 else v for k, v in
            #            list(request.args.to_dict(flat=False).items())}
            #criteria = {k: int(v) if "{}".format(v).isdigit() else v for k, v in list(criteria.items())}
            #c_is_alive = None
            is_alive = is_alive.lower()
            is_alive = True if is_alive == 'true' else False if is_alive == 'false' else None
            search_criteria = {'is_alive': is_alive}
            # if 'is_alive' in criteria:
            #     c = criteria['is_alive'].lower()
            #     c_is_alive = True if c == 'true' else False if c == 'false' else None
            #     if c_is_alive is not None:
            #         search_criteria.update({'is_alive':c_is_alive})

            tr_lst = myDb.get_fields(search_criteria, fields, collection='testruns',find_one=False)
            #if not tr_lst:
            #    search_criteria['status'] = 'READY'
            #    tr_lst = myDb.get_fields(search_criteria, fields, collection='testruns', find_one=False)
            #pid_dict = myDb.get_fields(runid, 'pid',collection='testruns')
            if not tr_lst: return resp
            for tr_dict in tr_lst:
                summary = {
                    'created_datetime': None,
                    'data': '{}',
                    'data_type': 'dict',
                    'elapsed_time': None,
                    'error_message': None,
                    'is_alive': False,
                    'num_of_testcases': None,
                    'num_of_unknown': 0,
                    'num_of_pass': 0,
                    'num_of_fail': 0,
                    'num_of_skip': 0,
                    'pid': None,
                    'report_path': None,
                    'runid':None,
                    'started_by': None,
                    'status': None,
                    'suitename': None,
                    'suitelabel': None,
                    'test_bed': None,
                    'updated_datetime': None,
                    # 'started_time': None,
                    # 'updated_time': None,
                    # 'run_timeout': 0,
                    # 'testcases': [],
                    # 'report_path': None,
                    # 'report_url': None
                }
                if tr_dict:
                    summary['is_alive'] = tr_dict['is_alive']
                    if summary['is_alive']:
                        summary['pid'] = tr_dict['pid']
                    summary['runid'] = str(tr_dict['runid'])
                    summary['created_datetime'] = '' if not tr_dict['created_datetime'] else tr_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
                    summary['elapsed_time'] = tr_dict['elapsed_time']
                    summary['error_message'] =  tr_dict['error_message']
                    #summary['started_time'] = '' if tr_dict is None else tr_dict['started_time']

                    #summary['run_timeout'] = None if tr_dict is None else tr_dict['run_timeout']
                    summary['report_path'] = tr_dict['report_path']
                    summary['started_by'] = tr_dict['started_by']
                    summary['status'] = tr_dict['status']
                    if summary['status'] == 'READY': summary['status'] = 'STARTED'
                    if summary['status'] is None or summary['status'] not in Templates.TESTRUN_STATUS:
                        summary['status'] = 'UNKNOWN'
                    summary['suitename'] = tr_dict['testsuite']
                    summary['suitelabel'] = tr_dict['suitelabel']
                    summary['test_bed'] = tr_dict['testbed']
                    summary['updated_datetime'] = '' if not tr_dict['updated_datetime'] else tr_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
                    summary.update(TestCase.get_testcase_stats(int(summary['runid']), myDb))
                resp.append(summary)
            myDb.close()
            return resp, 200
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get alive testruns, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get alive testruns because of exception: {} traceback={}'.format(e, helper.get_traceback ())})
            resp.status_code = 400
            return resp

# endpoint to view log in text
#@api.route('/view_log/<path:log>')
@api.route('/view_log')
@api.doc(params={'path': 'log path'})
class viewLog(Resource):
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self):
        '''
        Description: Get testrun status
        '''
        log_path = request.args.get('path', '')
        print(("view log at: {}".format(log_path)))
        try:
            if log_path == None:
                return {'status': 'log not found: {}'.format(log_path)}, 400
            else:
                return send_from_directory(os.path.dirname(log_path), os.path.basename(log_path),
                                           mimetype='text/plain', as_attachment=False)

        except Exception as e:
            print ("failed to view log, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to view log because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

# endpoint to view log in html
@api.route('/view_log_html')
@api.doc(params={'path': 'log path'})
class viewLogHtml(Resource):
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self):
        '''
        Description: Get testrun status
        '''
        log_path = request.args.get('path', '')
        print(("view log at: {}".format(log_path)))
        try:
            if log_path == None:
                return {'status': 'log not found: {}'.format(log_path)}, 400
            else:
                return send_from_directory(os.path.dirname(log_path), os.path.basename(log_path),
                                           mimetype='text/html', as_attachment=False)
        except Exception as e:
            print ("failed to view html log, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to view log because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

@app.route('/browse_dir')
def browseDir():
    dir_path = request.args.get('path', '').rstrip ('/')
    dirname = os.path.dirname (dir_path)
    basename = os.path.basename (dir_path)
    extension = basename.split ('.')[-1]
    endpoint = '.browseDir'
    try:
        if os.path.isdir (dir_path):
            #return rootdir.render_autoindex(dir_path, endpoint=endpoint)
            return rootdir.render_autoindex(dir_path, endpoint=endpoint).replace ('>Parent folder</a>',
                  '''>Parent folder</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="/zip_dir?path={}" download="{}.zip">Download folder: {}.zip</a>'''.format (dir_path, basename, basename)
                  )
        #else:
            #return get_file_content_response (dir_path)

        elif extension in ['txt','py','log', 'yaml', 'gts', 'gtc', 'prm', 'json']:
            return send_file (dir_path, download_name=basename, mimetype='text/plain')
        elif extension in ['html']:
            return send_file(dir_path, download_name=basename, mimetype='text/html')
        else:
            return send_file (dir_path, download_name=basename, as_attachment=True)

    except Exception as e:
        return make_response ("{}".format (e), 404)

@app.route('/results/<path:path_to_results>')
def results(path_to_results):
    dir_path = path_to_results.replace('GigatestLogs', Constants.GIGATEST_LOGS_PATH)
    dirname = os.path.dirname (dir_path)
    basename = os.path.basename (dir_path)
    extension = basename.split ('.')[-1]
    endpoint = '.browseDir'
    try:
        if os.path.isdir (dir_path):
            #return rootdir.render_autoindex(dir_path, endpoint=endpoint)
            return rootdir.render_autoindex(dir_path, endpoint=endpoint).replace ('>Parent folder</a>',
                  '''>Parent folder</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="/zip_dir?path={}" download="{}.zip">Download folder: {}.zip</a>'''.format (dir_path, basename, basename)
                  )
        #else:
            #return get_file_content_response (dir_path)

        elif extension in ['txt','py','log', 'yaml', 'gts', 'gtc', 'prm', 'json']:
            return send_file (dir_path, download_name=basename, mimetype='text/plain')
        elif extension in ['html']:
            return send_file(dir_path, download_name=basename, mimetype='text/html')
        else:
            return send_file (dir_path, download_name=basename, as_attachment=True)

    except Exception as e:
        return make_response ("{}".format (e), 404)

@app.route('{}/<path:path_to_source>'.format(BASE_PATH))
def browse_source(path_to_source):
    dir_path = '{}/{}'.format(BASE_PATH, path_to_source) #path_to_results.replace('GigatestLogs', '/mnt/automation/GigatestLogs')
    dirname = os.path.dirname (dir_path)
    basename = os.path.basename (dir_path)
    extension = basename.split ('.')[-1]
    endpoint = '.browseDir'
    try:
        if os.path.isdir (dir_path):
            #return rootdir.render_autoindex(dir_path, endpoint=endpoint)
            return rootdir.render_autoindex(dir_path, endpoint=endpoint).replace ('>Parent folder</a>',
                  '''>Parent folder</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="/zip_dir?path={}" download="{}.zip">Download folder: {}.zip</a>'''.format (dir_path, basename, basename)
                  )
        #else:
            #return get_file_content_response (dir_path)

        elif extension in ['txt','py','log', 'yaml', 'gts', 'gtc', 'prm', 'json', 'robot']:
            return send_file (dir_path, download_name=basename, mimetype='text/plain')
        elif extension in ['html']:
            return send_file(dir_path, download_name=basename, mimetype='text/html')
        else:
            return send_file (dir_path, download_name=basename, as_attachment=True)

    except Exception as e:
        return make_response ("{}".format (e), 404)

# endopoint to get testcase status from a testrun
@api.route('/get_testcase_status/<string:runid>/<string:testcase_name>')
class GetTestcaseStatus(Resource):
    #@api.expect(Model.test_run_status)
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid, testcase_name):
        '''
        Description: Get testrun status
        '''
        runid = int(runid)

        testcase = {
            'created_datetime': '',
            #'end_time': None,
            'ended_time': None,
            #'error': '',
            'log_file': '', #'/mnt/automation/GigatestLogs/master/462474/7880760/runReg.125650/log.html',
            'logs':[],
            'message': '',
            'name': '', #'Validate Vseries DHCP IP Node deployment with Small-Medium and Thin',
            'pathname': '', #'Validate Vseries DHCP IP Node deployment with Small-Medium and Thin',
            'result': '',
            'runid':'',
            #'result_color': '', #'#66cc66',
            'sequence': 0,
            'sid': 0,
            'start_time': '', #'Fri, 21 Jun 2024 13:26:20 GMT',
            'status': '', #'FINISHED',
            #'status_color': '', #'#4775d1',
            #'subtests': '',
            'testcase_id': None, #'63ce6fd5',
            'title': '', #'Cloud Functional.Hybrid.6.3.00.vmwareEsxi.Sanity.Testcases',
            'type': 'Robot',
            'updated_datetime':''
            }
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)
            tr_dict = myDb.get_fields(runid, ['log-path'], collection='testruns')
            tc_fields = ['testname',
                         'longname',
                         'status',
                         #'sequence',
                         #'sid',
                         'result',
                         'type',
                         'testmetadata',
                         'created_datetime',
                         'updated_datetime'
                         ]
            tc_dict = myDb.get_fields({'runid':runid,'longname':testcase_name}, tc_fields, collection='testcases')
            if not tc_dict: raise Exception("Cannot find {} testcase".format(testcase_name))
            testcase['created_datetime'] = tc_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            testcase['updated_datetime'] = tc_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            if 'endtime' in tc_dict['testmetadata']: testcase['ended_time'] = tc_dict['testmetadata']['endtime']
            #testcase['error'] = tc_dict['testmetadata']['message'] if tc_dict['result'] not in ['PASS'] else ''
            testcase['log_file'] = '{}/log.html#{}'.format(tr_dict['log-path'],tc_dict['testmetadata']['id'])
            testcase['message'] = tc_dict['testmetadata']['message']
            testcase['name'] = tc_dict['longname'] #tc_dict['testname']
            testcase['pathname'] = tc_dict['testmetadata']['longname']
            testcase['result'] = tc_dict['result']
            testcase['runid'] = str(runid)
            #testcase['result_color'] = helper.get_color_status(tc_dict['result'])
            if 'starttime' in tc_dict['testmetadata']: testcase['start_time'] = tc_dict['testmetadata']['starttime']
            testcase['status'] = tc_dict['status']
            #testcase['status_color'] = helper.get_color_status(tc_dict['status'])
            testcase['testcase_id'] = tc_dict['testmetadata']['id']
            testcase['title'] = tc_dict['longname']
            testcase['type'] = tc_dict['type']

            #summary['testcases'].extend(value for d in tc_dict for value in d.values())
            #summary.update(TestCase.get_testcase_stats(runid, myDb))
            myDb.close()
            resp = jsonify(testcase)
            helper.set_no_cache(resp)
            resp.status_code = 200
            return resp
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get testcase status, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get testcase status because of exception: {} traceback={}'.format(e, helper.get_traceback ())})
            resp.status_code = 400
            return resp
# get testcase details from  a testrun
@api.route('/get_testcase_details/<string:runid>/<string:testcase_name>')
class GetTestcaseDetails(Resource):
    # @api.expect(Model.test_run_status)
    @api.marshal_with(Model.testcase_details, envelope='testcase_details')
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid, testcase_name):
        '''
        Description: Get testrun status
        '''
        runid = int(runid)

        testcase = {
            'created_datetime': '',
            'log_file': '', #'/mnt/automation/GigatestLogs/master/462474/7880760/runReg.125650/log.html',
            'logs':[],
            'name': '', #'Validate Vseries DHCP IP Node deployment with Small-Medium and Thin',
            'result': '',
            'runid':'',
            'sequence': 0,
            'sid': 0,
            'status': '', #'FINISHED',
            'type': 'Robot',
            'updated_datetime':''
            }
        try:
            myDb = Mongo()
            ### get testrun pid and status ###
            TestRun.update_testrun_is_alive(runid, db=myDb)
            tr_dict = myDb.get_fields(runid, ['log-path'], collection='testruns')
            tc_fields = ['testname',
                         'longname',
                         'status',
                         #'sequence',
                         #'sid',
                         'result',
                         'type',
                         'testmetadata',
                         'created_datetime',
                         'updated_datetime'
                         ]
            tc_dict = myDb.get_fields({'runid':runid,'longname':testcase_name}, tc_fields, collection='testcases')
            if not tc_dict: raise Exception ("Cannot find {} testcase".format(testcase_name))
            testcase['created_datetime'] = tc_dict['created_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            testcase['updated_datetime'] = tc_dict['updated_datetime'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            #testcase['ended_time'] = tc_dict['testmetadata']['endtime']
            #testcase['error'] = tc_dict['testmetadata']['message'] if tc_dict['result'] not in ['PASS'] else ''
            testcase['log_file'] = '{}/log.html#{}'.format(tr_dict['log-path'],tc_dict['testmetadata']['id'])
            #testcase['message'] = tc_dict['testmetadata']['message']
            testcase['name'] = tc_dict['longname'] #tc_dict['testname']
            #testcase['pathname'] = tc_dict['testmetadata']['longname']
            testcase['result'] = tc_dict['result']
            testcase['runid'] = str(runid)
            #testcase['result_color'] = helper.get_color_status(tc_dict['result'])
            #testcase['start_time'] = tc_dict['testmetadata']['starttime']
            testcase['status'] = tc_dict['status']
            #testcase['status_color'] = helper.get_color_status(tc_dict['status'])
            #testcase['testcase_id'] = tc_dict['testmetadata']['id']
            #testcase['title'] = tc_dict['longname']
            testcase['type'] = tc_dict['type']

            #summary['testcases'].extend(value for d in tc_dict for value in d.values())
            #summary.update(TestCase.get_testcase_stats(runid, myDb))
            myDb.close()
            #resp = jsonify(testcase)
            #helper.set_no_cache(resp)
            #resp.status_code = 200
            return testcase, 200
        except Exception as e:
            if myDb: myDb.close()
            print ("failed to get testcase details, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = {'status': 'failed to get testcase details because of exception: {} traceback={}'.format(e, helper.get_traceback ())}
            #resp.status_code = 400
            return resp, 400

@app.route('/stream', methods=['GET'])
def stream():
    portal_log = request.args.get("agent_log")
    if os.path.exists("/tmp/{}".format(portal_log)):
        log_path = "/tmp/{}".format(portal_log)
    elif os.path.exists("/var/log/{}".format(portal_log)):
        log_path = "/var/log/{}".format(portal_log)
    else:
        return jsonify({"content": "failed to retrieve log", "num_lines": 1})
    f = open(log_path)
    content = f.readlines()
    return jsonify({"content": content, "num_lines": len(content)})

@app.route('/get_all_test_runs', methods=['GET'])
def getAllTestRuns():
    run_record = {}
    mydb = Mongo()
    all_tests = mydb.find_all_test_runs()
    for job in all_tests:
        run_date = "{}-{}".format(job['created_datetime'].month,job['created_datetime'].day)
        if run_date in run_record:
            run_record[run_date] = run_record[run_date] + 1
        else:
            run_record[run_date] = 1

    resp = jsonify({"test_runs":run_record})

    return resp

@app.route('/pull_repo', methods=['GET'])
def pullRepo():
    repo_name = request.args.get("repo")
    repo_dir = "/{}".format(request.args.get("repo_dir"))
    try:
        repo = git.Repo(repo_dir)
        origin = repo.remotes.origin
        origin.pull()
    except Exception as e:
        print(("failed to pull from repo: {} because of {}".format(repo_name, e)))
        resp = jsonify({"message":"failed to pull from repo: {} because of {} traceback={}".format(repo_name, e, helper.get_traceback())})
        resp.status_code = 400
        return resp
    resp = jsonify({"message":"success"})

    return resp

@app.route('/get_repo', methods=['GET'])
def getRepo():
    repos = []
    content = []
    base_path = request.args.get("base_path")
    direstories = glob("{}/*".format(base_path))
    for item in direstories:
        try:
            repos.append(git.Repo(item))
        except Exception:
            app.logger.warning("{} is not a git repository".format(item))
            pass

    for repo in repos:
        details = {}
        details['directory'] = repo.working_dir
        details['repo_name'] = repo.working_dir.split('/')[-1]
        details['branch'] = repo.active_branch.name
        details['path'] = repo.active_branch.path
        details['log'] = [(entry.message, entry.actor.name, time.strftime("%a, %d %b %Y %H:%M",time.localtime((entry.time[0]))))
                          for entry in repo.active_branch.log()]
        details['author'] = repo.commit().author.name
        details['last_committ_summary'] = repo.commit().summary
        details['time'] = time.strftime("%a, %d %b %Y %H:%M",time.localtime((repo.commit().authored_date)))
        content.append(details)


    return jsonify(content)

# get log from a testcase of a testrun
@api.route('/get_logs/<string:runid>/<string:testcase_name>')
class GetTestcaseLog(Resource):
    #@api.expect(Model.test_case_logs)
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self, runid, testcase_name):
        '''
        Description: Get testcase logs
        '''
        runid = int(runid)



        #testcase = myDb.find_test_case(runid, testcase_name)
        try:
            myDb = Mongo()
            tc_fields = ['testmetadata']
            tr_dict = myDb.get_fields(runid, ['log-path'], collection='testruns')
            tc_dict = myDb.get_fields({'runid': runid, 'longname': testcase_name}, tc_fields, collection='testcases')
            if not tc_dict:
                return {'status': "{} not found".format(runid)}, 400
            else:
                #log_path = testcase[0]['log_file']
                log_path = '{}/log.html#{}'.format(tr_dict['log-path'], tc_dict['testmetadata']['id'])
                return send_from_directory(os.path.dirname(log_path), os.path.basename(log_path), mimetype='text/plain')
                #return {'logs': testcase[0]['logs']}, 200
        except Exception as e:
            print ("failed to get testcase log, encountered exception: {}".format(e, helper.get_traceback ()))
            resp = jsonify({'status': 'failed to get log because of exception: {} traceback={}'.format(e, helper.get_traceback())})
            resp.status_code = 400
            return resp

# get log from a testcase of a testrunxx
@api.route('/health_check')
class HealthCheck(Resource):
    # @api.expect(Model.test_case_logs)
    @api.response(200, Constants.OK)
    @api.response(400, Constants.FAILED)
    def get(self):
        '''
        Description: Health Check
        '''
        #random_string = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        try:
            myDb = Mongo()
            if myDb:
                print("health check ok")
                resp = jsonify({'health': 'ok'})
                resp.status_code = 200
                return resp
            else:
                raise
        except:
            print("health check failed")
            resp = jsonify({'health': 'failed'})
            resp.status_code = 400
            return resp



# Default when run under Apache
run_mode = Constants.RUN_MODE_THREAD
port_num = Constants.SERVER_PORT #8888 #80

# def startTestRun(arguments):#, logger):
#     #TestRunner.start(args, logger)
#     #p = StartTestRunProcess(args, logger)
#     #p.start()
#     p = Process(target=_startTestRun, args=(arguments,))
#     p.start()
#
# def _startTestRun(arguments):
#     print("asasas")
if __name__ == '__main__':
    #run_mode = Constants.RUN_MODE_THREAD
    #run_mode = Constants.RUN_MODE_SINGLE
    try:
        # parsing arguments
        parser = helper.parse_arg()
        params = parser.parse_args()

        # set port number and running mode
        port_num = params.port
        run_mode = params.mode
        print(("Mode: {} Port: {}".format(run_mode, port_num)))

        # run env
        run_env = params.env
        print(("Environment: {}".format(run_env)))

        # startup service
        app.run(host=params.ip, port=params.port, debug=False, threaded=True)
        print("Gigagent Started!")
    except Exception as e:
        raise Exception("Failed to start Gigagent! {}".format(e))
