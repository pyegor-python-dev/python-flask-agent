import json
import re
import shutil
import time
from copy import deepcopy
from datetime import datetime
from retrying import retry
import netifaces
import uuid
import argparse
import os, sys, traceback
import psutil
from pymongo.errors import ConnectionFailure
from pymongo import MongoClient
#from Gigatest.lib.db_interface import MongoDBInterface#, MongoClient
from Gigatest.lib.constants import Constants # as Constants
from Gigatest.lib.gigalogger import GLog#, Log
from regression.regClass import runRegression
#from rsyncwrap import rsyncwrap
import requests
from .http_request import Request

global server_ip

def get_traceback (msg=None):
    etype, value, tb = sys.exc_info()
    error = ''.join(traceback.format_exception(etype, value, tb))
    if msg:
        return "{}: {}".format (msg, error)
    else:
        return "{}".format (error)

def ConvertLstToDict(list):
    it = iter(list)
    rdict = dict(zip(it, it))
    return rdict

# class to hold retry determination functions
class Retry:
    @staticmethod
    def retry_if_rest_call_not_ok(response):
        # return False if the status code is not 200 or 201
        if response.status_code == 200 or response.status_code == 201:
            return False
        else:
            return True

    @staticmethod
    def retry_if_none(result):
        # return False if the status code is not 200 or 201
        if result == None:
            return True
        else:
            return False

class Mongo:
    '''
    Description: This class provides database connectivities to allow test run detail/status to be saved and retrieved
    '''

    def __init__(self, collection=None):
        '''
        Constructor to initialize database instance
        '''
        self.collection = None
        self.DOT_REPLACEMENT = "__dot__"
        self.client = MongoClient()
        try:
            # The ping command is cheap and does not require auth.
            self.client.admin.command('ping')
        except ConnectionFailure:
            raise ConnectionFailure ("MongoDB server is not available")
        try:
            #self.client = MongoClient()#'localhost:27017', connect=False)
            self.db = self.client.testrunsDB
        except Exception:
            raise Exception("Failed to connect to 'testrunsDB'")
        ## Create/get collection
        if collection:
            try:
                self.collection = self.db[collection]
            except Exception:
                raise Exception("Failed to create collection {}".format(collection))

    def __enter__ (self):
        return self

    def __exit__ (self, *args):
        self.client.close ()

    def close (self):
        self.client.close ()



    def encode_keys(self, obj):
        """Recursively replace dots in dictionary keys with a safe string."""
        if isinstance(obj, dict):
            return {
                key.replace('.', self.DOT_REPLACEMENT): self.encode_keys(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [self.encode_keys(item) for item in obj]
        else:
            return obj

    def decode_keys(self, obj):
        """Recursively restore dots in dictionary keys from the safe string."""
        if isinstance(obj, dict):
            return {
                key.replace(self.DOT_REPLACEMENT, '.'): self.decode_keys(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [self.decode_keys(item) for item in obj]
        else:
            return obj

    def add_to_db(self, filter, args, check_if_exists=False, collection=None):
        '''
        Description: Method to add new record to MongoDb
        :args: args dict with runid field required
        :return: raise exception when insert fails
        '''
        #runid = args['runid']
        #if not suitelabel: suitelabel = TESTSUITE().suite_label
        if type(filter) is int:
            find_opt = {'runid':filter}
        elif type(filter) is dict:
            find_opt = filter
            find_opt = self.encode_keys(find_opt)
        if '_id' in args:
            del args['_id']
        #q = self.collection.count_documents (find_opt)
        if collection is None and self.collection is None:
            raise Exception("helper.Mongo.add_to_db: Cannot get a collection")
        if collection:
            col_obj = self.db[collection]
        else:
            col_obj = self.collection
        if check_if_exists and col_obj.count_documents (find_opt) > 0:
            return ("helper.Mongo.add_to_db: a DB record for runid {} already exists".format(find_opt))
            #self.update_testrun_status(runid, Constants.STARTED)
        args['created_datetime'] = datetime.now()  # '12345'#time.strftime('%m/%d/%y %H:%M:%S')
        args = self.encode_keys(args)
        col_obj.insert_one (args)
        if col_obj.count_documents (find_opt) <= 0:
            raise Exception("helper.Mongo.add_to_db: could not add {} record to DB".format(find_opt))
        return 0

    def count_docs (self, filter, collection=None):
        if collection is None and self.collection is None:
            raise Exception("helper.Mongo.count_docs: Cannot get a collection")
        if collection:
            col_obj = self.db[collection]
        else:
            col_obj = self.collection
        if type(filter) is int:
            find_opt = {'runid':filter}
        elif type(filter) is dict:
            find_opt = filter
            find_opt = self.encode_keys(find_opt)
        else:
            raise Exception ("invalid runid var type")
        return col_obj.count_documents (find_opt)

    def get_fields (self, filter, fields, collection=None, find_one=True, _id=False):
        if collection is None and self.collection is None:
            raise Exception("helper.Mongo.count_docs: Cannot get a collection")
        if collection:
            col_obj = self.db[collection]
        else:
            col_obj = self.collection
        if type(filter) is int:
            find_opt = {'runid':filter}
        elif type(filter) is dict:
            find_opt = filter
            find_opt = self.encode_keys(find_opt)
        else:
            raise Exception ("invalid runid var type")
        if _id:
            query = {'_id':1}
        else:
            query = {'_id':0}
        if type(fields) is str:
            query[fields] = 1
        elif type(fields) is list:
            for field in fields:
                query[field] = 1
        else:
            raise Exception('Invalid "fields" type')
        if find_one:
            return self.decode_keys(col_obj.find_one (find_opt, query))
        else:
            tcs = []
            for tc in col_obj.find(find_opt, query):
                tcs.append(tc)
            tcs = self.decode_keys(tcs)
            return tcs


    def update_db(self, selector, args, collection=None):
        '''
        Description: Method to update a MongoDBdocument
        :args: args dict to update with runid field required
        :return: raise exception when insert fails
        '''
        #runid = args['runid']
        if collection is None and self.collection is None:
            raise Exception("helper.Mongo.update_db: Cannot get a collection")
        if collection:
            col_obj = self.db[collection]
        else:
            col_obj = self.collection
        if type(selector) is int:
            find_opt = {'runid':selector}
        elif type(selector) is dict:
            find_opt = selector
            find_opt = self.encode_keys(find_opt)
        else:
            raise Exception ("invalid runid var type")
        #if not suitelabel: suitelabel = TESTSUITE().suite_label
        if col_obj.count_documents (find_opt) > 0:
            #args['updated_datetime'] = datetime.now()
            args = self.encode_keys(args)
            col_obj.update_one(find_opt, args)
            col_obj.update_one(find_opt, {'$set':{'updated_datetime':datetime.now()}})
            #self.update_testrun_status(runid, Constants.STARTED)
        else:
            print ("helper.Mongo.update_db: required DB record  not found. find_opt: {}, args: {}".format(find_opt, args)) #raise Exception

    def delete_db(self, selector, collection=None):
        '''
        Description: Method to delete a MongoDBdocument
        :args: args dict to update with runid field required
        :return: raise exception when insert fails
        '''
        #runid = args['runid']
        if collection is None and self.collection is None:
            raise Exception("helper.Mongo.delete_db: Cannot get a collection")
        if collection:
            col_obj = self.db[collection]
        else:
            col_obj = self.collection
        if type(selector) is int:
            find_opt = {'runid':selector}
        elif type(selector) is dict:
            find_opt = selector
            find_opt = self.encode_keys(find_opt)
        else:
            raise Exception ("invalid runid or search criteria var type")
        #if not suitelabel: suitelabel = TESTSUITE().suite_label
        if col_obj.count_documents (find_opt) > 0:
            #args['updated_datetime'] = datetime.now()
            #args = self.encode_keys(args)
            col_obj.delete_many(find_opt)
            #col_obj.update_one(find_opt, {'$set':{'updated_datetime':datetime.now()}})
            #self.update_testrun_status(runid, Constants.STARTED)
        else:
            print ("helper.Mongo.delete_db: required DB record  not found. find_opt: {}".format(find_opt)) #raise Exception
    #def find_re
    # def find_test_run_by_status(self, status):
    #     '''
    #     Description: Method to find test run by status
    #     :param runid: string, test run identifier
    #     :param status: string, "FINISHED" or "STARTED"
    #     :return: list of testruns
    #     '''
    #     test_runs = self.collection.find({'status': status})
    #     test_runs = self.decode_keys(test_runs)
    #     return test_runs

class HelperMethods(object):
    '''
    Description: helper functions for gigagent
    '''
    @staticmethod
    def delete_file(file_path):
        # Check if the file exists, then delete it
        if os.path.exists(file_path):
            os.remove(file_path)
        return True

    @staticmethod
    def get_color_status(status):
        return Constants.COLOR[status] if status in Constants.COLOR else Constants.COLOR['UNKNOWN']

    @staticmethod
    def export_env_vars(env_dict):
        for var_nm in env_dict:
            os.environ[var_nm] = env_dict[var_nm]
            # if var_nm == 'PATH' or var_nm == 'PYTHONPATH':
            #     if var_nm in os.environ:
            #         if env_dict[var_nm] in os.environ[var_nm]: continue
            #         os.environ[var_nm] += env_dict[var_nm]
            #     else:
            #         os.environ[var_nm] = env_dict[var_nm]
            # else:
            #     #if var_nm not in os.environ:
            #     os.environ[var_nm] = env_dict[var_nm]
        return True

    @staticmethod
    def get_logger(log_path, log_name):
        return GLog ("{}/{}".format (log_path, log_name))


    @staticmethod
    def get_traceback(msg=None):
        etype, value, tb = sys.exc_info()
        error = ''.join(traceback.format_exception(etype, value, tb))
        if msg:
            return "{}: {}".format(msg, error)
        else:
            return "{}".format(error)

    @staticmethod
    def is_process_alive(pid):
        """ Check For the existence of a unix pid. """
        if not pid: return False
        try:
            process = psutil.Process(pid)
            return process.status() != psutil.STATUS_ZOMBIE
        except:
            return False

    # return a uuid to use for run tag
    @staticmethod
    def get_run_id():
        print("generating runid ...")
        return str(uuid.uuid4())

    ## get SW version out of given build id
    @staticmethod
    def get_build_swversion (build=None):
        if not build: return None
        for i in range(3):
            try:
                res = Request ('https://esportal.gigamon.com/api/builds').get ('get_build', build_number=build, attrs='version')
                if res and 'version' in res[0]: return res[0]['version'].split("_")[0]
            except Exception as e:
                print ("{}".format (get_traceback(msg="{}".format (e))))
                time.sleep (5)
        return None
    # get local ip address
    @staticmethod
    def get_server_ip():
        interfaces = netifaces.interfaces()
        for i in interfaces:
            if not (i.startswith('eth') or i.startswith('en')):
                continue
            iface = netifaces.ifaddresses(i).get(netifaces.AF_INET)
            if iface != None:
                for j in iface:
                    if j['addr'].startswith("10."):
                        print(("found server ip {}".format(j['addr'])))
                        return j['addr']
        return '127.0.0.1'

    # parsing payload from submitted body and construct list of arguments
    @staticmethod
    def export_taf_envvar (arguments):
        # get list of Robot parameters from TAF framework
        #for envvar in arguments['test_param'][1]['envar']:
        #    HelperMethods.export_env_vars({envvar: arguments['test_param'][1]['envar'][envvar]})
        if 'TAF_HOME' in arguments['test_param'][1]['envar']:
            #os.environ['TAF_HOME'] = arguments['test_param'][1]['envar']['TAF_HOME']
            HelperMethods.export_env_vars({'TAF_HOME':arguments['test_param'][1]['envar']['TAF_HOME']})
        if 'HOME' in arguments['test_param'][1]['envar']:
            #os.environ['HOME'] = arguments['test_param'][1]['envar']['HOME']
            HelperMethods.export_env_vars({'HOME': arguments['test_param'][1]['envar']['HOME']})
        if 'PYTHONPATH' in arguments['test_param'][1]['envar']:
            #os.environ['PYTHONPATH'] += arguments['test_param'][1]['envar']['PYTHONPATH']
            HelperMethods.export_env_vars({'PYTHONPATH': arguments['test_param'][1]['envar']['PYTHONPATH']})
        if 'PATH' in arguments['test_param'][1]['envar']:
            #os.environ['PYTHONPATH'] += arguments['test_param'][1]['envar']['PYTHONPATH']
            HelperMethods.export_env_vars({'PATH': arguments['test_param'][1]['envar']['PATH']})
    #@staticmethod
    # def get_taf_robot_params(arguments):
    #     inputData, _ = HelperMethods._get_taf_inputdata(deepcopy(arguments), robot_dryrun=True)
    #     HelperMethods._taf_runner(inputData, 'standardReg')
    #     if 'CMD_OPTIONS' not in os.environ:
    #         raise Exception ("regClass regression dry-run failed. 'CMD_OPTIONS' env variable has not been set")
    #     robot_params = eval(os.environ['CMD_OPTIONS'])
    #     #robot_params = robot_params[1:]
    #     #robot_params = ConvertLstToDict(robot_params)
    #     return robot_params



    @staticmethod
    def _get_taf_inputdata (arguments, robot_dryrun):
        if 'REG_TYPE' in arguments['test_param'][0]['data']:
            reg_type = arguments['test_param'][0]['data']['REG_TYPE']
        elif 'REG_TYPE' in arguments['test_param'][0]['data']['variables']:
            reg_type = arguments['test_param'][0]['data']['variables']['REG_TYPE']
        else:
            reg_type = 'standardReg'
        if reg_type not in ['standardReg', 'developerReg']:
            raise Exception ("Unsupported regression type. 'REG_TYPE' must be either 'standardReg' or 'developerReg'")
        if 'regList' not in arguments['test_param'][0]['data']:
            raise Exception ("'regList' parameter is not defined")
        if len(arguments['test_param'][0]['data']['regList']) > 1:
            raise Exception ("Multiple regressions are not supported in current Gigatest-TAF wrapper. 'regList' must have only one item")

        inputData = arguments['test_param'][0]['data']
        if 'variables' not in inputData:
            inputData['variables'] = {}
        inputData['variables']['RUN_ID'] = arguments['run-tag']
        inputData['outputdir'] = arguments['log-path']
        ### Dryrun settings ###
        inputData['dryrun'] = False
        inputData['robot_dryrun'] = robot_dryrun
        inputData['variables']['ROBOT_DRYRUN'] = robot_dryrun
        return inputData, reg_type

    @staticmethod
    def _taf_runner (inputData, regType, logger):
        reg = runRegression(regType, inputData, logger)
        reg.runAllRegression()
    # @staticmethod
    # def _taf_run_setup (arguments, robot_dryrun, export_env_var):
    #     if 'REG_TYPE' in arguments['test_param'][0]['data']:
    #         reg_type = arguments['test_param'][0]['data']['REG_TYPE']
    #     elif 'REG_TYPE' in arguments['test_param'][0]['data']['variables']:
    #         reg_type = arguments['test_param'][0]['data']['variables']['REG_TYPE']
    #     else:
    #         reg_type = 'standardReg'
    #     if reg_type not in ['standardReg', 'developerReg']:
    #         raise Exception ("Unsupported regression type. 'REG_TYPE' must be either 'standardReg' or 'developerReg'")
    #     if 'regList' not in arguments['test_param'][0]['data']:
    #         raise Exception ("'regList' parameter is not defined")
    #     if len(arguments['test_param'][0]['data']['regList']) > 1:
    #         raise Exception ("Multiple regressions are not supported in current Gigatest-TAF wrapper. 'regList' must have only one item")
    #
    #     inputData = arguments['test_param'][0]['data']
    #     if 'variables' not in inputData:
    #         inputData['variables'] = {}
    #     inputData['variables']['RUN_ID'] = arguments['run-tag']
    #     inputData['outputdir'] = arguments['log-path']
    #     ### Dryrun settings ###
    #     inputData['dryrun'] = False
    #     inputData['robot_dryrun'] = robot_dryrun
    #     inputData['variables']['ROBOT_DRYRUN'] = robot_dryrun
    #
    #     ### Export env variables that TAF req ###
    #     if export_env_var:
    #         HelperMethods.export_taf_envvar(arguments)
    #     # if 'variables' in inputData:
    #     #     if 'BUILD_INFO' in inputData['variables']:
    #     #         del inputData['variables']['BUILD_INFO']
    #
    #     #reg = RunTAFRegression('standardReg', inputData)
    #     reg = runRegression('standardReg', inputData)
    #     reg.runAllRegression()
    #     #if 'CMD_OPTIONS' not in os.environ:
    #     #    raise Exception ("regClass regression dry-run failed. 'CMD_OPTIONS' env variable has not been set")
    #     #robot_params = eval(os.environ['CMD_OPTIONS'])
    #     #robot_params = robot_params[1:]
    #     #robot_params = ConvertLstToDict(robot_params)
    #     #return robot_params


    @staticmethod
    def parse_args(payload):
        #print(("payload: {}".format(payload)))
        #if 'xml' in payload:
        #    (payload['testsuite'], payload['email'], payload['test_param']) = helper.parse_xml(api.payload['xml'])
        if 'call_back_url' not in payload: raise Exception ("Missing 'call_back_url' filed in payload")
        if 'build' not in payload: raise Exception ("Missing 'build' id field in payload")
        if not payload['build']: raise Exception ("'build' cannot be empty")
        #call_back_url = payload.get('call_back_url')

        # if log-path is passed, make sure it's existed

        #logger = get_logger()

        #logger.info ('start_run request payload: {}'.format(api.payload))



        arguments = []
        if not "run-tag" in payload:
            runid = HelperMethods.get_run_id()
            payload["run-tag"] = runid
        #else:
        #    runid = api.payload["run-tag"]

        if "started_by" not in payload:
            payload['started_by'] = None

        if "test_type" not in payload:
            payload["test_type"] = 'taf'

        if payload['test_type'] not in ['robot', 'taf']:
            raise Exception("Unsupported test type '{}'".format(payload['test_type']))

        if "run_timeout" not in payload:
            payload['run_timeout'] = Constants.DEFAULT_TIMEOUT
        if not payload['run_timeout']: payload['run_timeout'] = Constants.DEFAULT_TIMEOUT

        if 'testsuite' not in payload or 'test_param' not in payload:
            raise Exception("Missing 'testsuite' or/and 'test_param' parameters in payload ")

        try:
            swversion = HelperMethods.get_build_swversion(payload['build'])
        except:
            swversion = ''

        arguments = {}
        for argument in payload:
            if 'custom_params' in argument:
                try:
                    arguments[argument] = json.loads(payload[argument])
                except Exception as e:
                    raise Exception("Error loading JSON in 'custom_params' in payload: {}".format(e.args[0]))
        if 'custom_params' not in arguments:
            arguments['custom_params'] = {}
        if '__SWVersion__' not in arguments['custom_params']:
            arguments['custom_params']['__SWVersion__'] = swversion
        elif arguments['custom_params']['__SWVersion__']:
            swversion = arguments['custom_params']['__SWVersion__']

        for argument in payload:
            if 'test_param' in argument:
                arguments[argument] = []
                    #    pass
                    #data = data.replace('BUILD_VERSION', arguments['custom_params']['__SWVersion__'])
                for tpset in payload[argument]:
                    if '--data' in tpset and '--env' in tpset:
                        obj = re.search('--data\s+(.*)\s+--envar\s+(.*)', tpset)
                        if obj:
                            data = '{' + '"data":{}'.format(obj.group(1)) + '}'
                            data = data.replace("'", '"')
                            data = data.replace('"True"', 'true')
                            data = data.replace('True', 'true')
                            data = data.replace('"False"', 'false')
                            data = data.replace('False', 'false')
                            if swversion:
                                data = data.replace('BUILD_VERSION', swversion)
                            envar = '{' + '"envar":{}'.format(obj.group(2)) + '}'
                            envar = envar.replace("'", '"')
                        else:
                            raise Exception('Missing --data and/or --env in test_params')
                    else:
                        raise Exception('Missing --data and/or --env in test_params')
                    try:
                        arguments[argument].append(json.loads(data)) #test_params = json.loads(tpset)
                        arguments[argument].append(json.loads(envar))
                    except Exception as e:
                        raise Exception("Error loading JSON in 'test_param' in payload: {}".format(e.args[0]))
            elif 'custom_params' in argument:
                continue
            else:
                arguments[argument] = payload[argument]
        arguments['test_param'][0]['data']['listeners'] = ['RunInfoGigagent']
        return arguments

        #arguments = ['--{}={}'.format(key, value) for key, value in list(payload.items()) if key not in
        #            ['test_file', 'testsuite', 'test_param', 'model', 'build_url', 'resource', 'library_path', 'suite_owner_contact', 'env_owner_contact', 'qa_contact',
        #             'run-tag', 'xml', 'call_back_url', 'owner', 'started_by', 'test_type', 'rerun_tests', 'changed_files'] and value not in ['string', 0]]

        #myDb = Mongo(logger=logger)

        #global run_idetifier

        #arguments.append(payload['testsuite'])
        #arguments.extend(payload['test_param'])
        #arguments.append("--resource={}".format(payload['resource']))

        #return (arguments, call_back_url)

    # parse options for robot tests
    @staticmethod
    def parse_robot_options(options, arguments):
        update_options = options
        for item in arguments:
            if '-testbed' in item:
                testbed_opt = item.split("-testbed")[1].split(" -")[0]
                update_options.append(('--testbed', testbed_opt.replace("'","").replace('"', '')))
            if '-logicalTopology' in item:
                lTopology_opt = item.split("-logicalTopology")[1].split(" -")[0].strip()
                update_options.append(('--logical-topology', lTopology_opt.replace("'","").replace('"', '')))
                update_options.append(('--clean', ''))
            if '-initDevices' in item:
                iDevices_opt = item.split("-initDevices")[1].split(" -")[0].strip()
                update_options.append(('--init-devices', iDevices_opt.replace("'","").replace('"', '')))
            if '-debugCmdFile' in item:
                debug_opt = item.split("-debugCmdFile")[1].split(" -")[0].strip()
                update_options.append(('--debug-cmd-file', debug_opt.replace("'","").replace('"', '')))
            if '-licenseFile' in item:
                license_opt = item.split("-licenseFile")[1].split(" -")[0].strip()
                update_options.append(('--licenseFile', license_opt.replace("'","").replace('"', '')))
            if '-emailPrefix' in item:
                emailpre_opt = item.split("-emailPrefix")[1].split(" -")[0].strip()
                update_options.append(('--email-prefix', emailpre_opt.replace("'","").replace('"', '')))
            if '-cleanProc' in item:
                cleanproc_opt = item.split("-cleanProc")[1].split(" -")[0].strip()
                update_options.append(('--clean-proc', cleanproc_opt.replace("'","").replace('"', '')))
            if '-cleanArgs' in item:
                cleanargs_opt = item.split("-cleanArgs")[1].split(" -")[0].strip()
                update_options.append(('--clean-args', cleanargs_opt.replace("'","").replace('"', '')))
            if '-mailto' in item:
                mailto_opt = item.split("-mailto")[1].split(" -")[0].strip()
                update_options.append(('--email', mailto_opt.replace("'","").replace('"', '')))
            if '-include' in item:
                include_opt = item.split("-include")[1].split(" -")[0].strip()
                update_options.append(('--include', include_opt.replace("'","").replace('"', '')))

        return update_options


    # parse args for robot tests
    @staticmethod
    def parse_robot_args(args):
        robot_args = []
        branch = None
        build = None
        print("parsing robot arguments")
        for param in args:
            if "--branch" in param:
                branch = param.split("=")[-1]
            elif "--build" in param:
                build = param.split("=")[-1]
        for param in args:
            if '-testbed' in param:
                robot_arg_mailto = re.split(r'(?:-mailto)\s*', param)[-1].split(' -')[0]
                robot_args = ['-mailto', robot_arg_mailto] + robot_args if robot_arg_mailto != '' and robot_arg_mailto != param else robot_args
                robot_arg_cleanArgs = re.split(r'(?:-cleanArgs)\s*', param)[-1].split(' -')[0]
                if branch and build:
                    robot_args = ['-cleanArgs', 'branchName:{} buildId:{} {}'.format(branch, build, robot_arg_cleanArgs.split("'")[1])] + robot_args if robot_arg_cleanArgs != '' and robot_arg_cleanArgs != param else robot_args
                else:
                    robot_args = ['-cleanArgs', robot_arg_cleanArgs] + robot_args if robot_arg_cleanArgs != '' and robot_arg_cleanArgs != param else robot_args
                robot_arg_cleanProc = re.split(r'(?:-cleanProc)\s*', param)[-1].split(' -')[0]
                robot_args = ['-cleanProc', robot_arg_cleanProc] + robot_args if robot_arg_cleanProc != '' and robot_arg_cleanProc != param else robot_args
                robot_arg_initDevices = re.split(r'(?:-initDevices)\s*', param)[-1].split(' -')[0]
                robot_args = ['-initDevices', robot_arg_initDevices.split("'")[1]] + robot_args if robot_arg_initDevices != '' and robot_arg_initDevices != param else robot_args
                robot_arg_clean = re.split(r'(?:-clean)\s*', param)[-1].split(' -')[0]
                robot_args = ['-clean'] + robot_args if 'Args' in robot_arg_clean or 'Proc' in robot_arg_clean else robot_args
                robot_arg_logicalTopology = re.split(r'(?:-logicalTopology)\s*', param)[-1].split(' -')[0]
                robot_args = ['-logicalTopology', robot_arg_logicalTopology] + robot_args if robot_arg_logicalTopology != '' and robot_arg_logicalTopology != param else robot_args
                robot_arg_testbed = re.split(r'(?:-testbed)\s*', param)[-1].split(' -')[0]
                robot_args = ['-testbed', robot_arg_testbed] + robot_args if robot_arg_testbed != '' else robot_args
                if len(re.split(r'(?:--test)\s*', param)) == 1:
                    pass
                else:
                    robot_arg_test = re.split(r'(?:--test)\s*', param)[-1].split(' -')[0]
                    robot_args = ['--test', robot_arg_test] + robot_args if robot_arg_test != '' and robot_arg_test != param else robot_args
            elif '.robot' in param:
                robot_args.append(param)
            print(("robot args: {}".format(robot_args)))
        return robot_args

    # # get call_back_url from argument list
    # @staticmethod
    # def get_call_back_url(args):
    #     for arg in args

    @staticmethod
    def _get_testsuites_params(run_data):
        parameters = []
        for topology in run_data:
            parameters.append(topology['@instance'])

        return parameters

    # parse xml to retrieve testrun details
    @staticmethod
    def parse_xml(xml_data):
        run_data = None
        buildinfo = xmltodict.parse(xml_data.decode("base64"))
        for node1 in buildinfo:
            for node2 in buildinfo[node1]:
                if buildinfo[node1][node2]['TopologyInstances'] != None:
                    run_data = (buildinfo[node1][node2]['@testsuite'],
                                buildinfo[node1][node2]['@to'],
                                helper._get_testsuites_params(buildinfo[node1][node2]['TopologyInstances']['Topology']))

        return run_data


    # make http POST call
    @staticmethod
    @retry(retry_on_result=Retry.retry_if_rest_call_not_ok, stop_max_attempt_number=5, wait_fixed=1000)
    def post_with_retry(url, payload):
        try:
            print(('post call: url: {} payload: {}'.format(url, payload)))
            response = requests.post(url, json=payload, verify=False)
        except Exception as e:
            raise Exception('failed to call {} with payload {} with error: {}, retrying ...'.format(url, payload, e))

        return response

    # make http GET call
    @staticmethod
    @retry(retry_on_result=Retry.retry_if_rest_call_not_ok, stop_max_attempt_number=5, wait_fixed=1000)
    def get_with_retry(url, params):
        endpoints = "{}/{}".format(url, params)
        try:
            print(('get call: {}'.format(endpoints)))
            response = requests.get(endpoints, verify=False)
        except Exception as e:
            raise Exception('failed to call {} with payload {} with error: {}, retrying ...'.format(url, params, e))

        return response

    @staticmethod
    def get(url, params, retry=True):
        if retry:
            response = HelperMethods.get_with_retry(url, params)
        else:
            endpoints = "{}/{}".format(url, params)
            try:
                print(('get call: {}'.format(endpoints)))
                response = requests.get(endpoints, verify=False)
            except Exception as e:
                raise Exception('failed to call {} with payload {} with error: {}'.format(url, params, e))

        return response

    # make http POST call
    @staticmethod
    def post(url, payload, retry=True):
        if retry:
            response = HelperMethods.post_with_retry(url, payload)
        else:
            try:
                print(('post call: url: {} payload: {}'.format(url, payload)))
                response = requests.post(url, json=payload, verify=False)
            except Exception as e:
                raise Exception ('failed to call {} with payload {} with error: {}'.format(url, payload, e))

        return response

    @staticmethod
    def delete_log_dir(dir_lst):
        for dir in dir_lst:
            try:
                shutil.rmtree(dir)
            except Exception as e:
                print(f"helper.delete_log_dir: Failed to delete {dir}: {e}")

    # init logging
    # @staticmethod
    # def init_log():
    #     try:
    #         log_base_dir = os.path.dirname(Constants.AGENT_LOG_PATH)
    #         log_filename = os.path.basename(Constants.AGENT_LOG_PATH)
    #         # log_console_base_dir = os.path.dirname(Constants.CONSOLE_LOG_PATH)
    #         # log_console_filename = os.path.basename(Constants.CONSOLE_LOG_PATH)
    #         if not os.path.isdir(log_base_dir):
    #             #os.makedirs(log_base_dir)
    #             cmd_util.makedirs(log_path)
    #
    #         # if not os.path.isdir(log_console_base_dir):
    #         #     os.makedirs(log_console_base_dir)
    #         #     cmd_util.makedirs(log_console_base_dir)
    #
    #         # if the user not allows to create logs from /var/log, create it under /tmp
    #         try:
    #             handler = RotatingFileHandler(Constants.AGENT_LOG_PATH, maxBytes=30000000, backupCount=10)
    #         except Exception as e:
    #             handler = RotatingFileHandler(os.path.join("/tmp", log_filename), maxBytes=30000000, backupCount=10)
    #
    #         # try:
    #         #     handler_console = RotatingFileHandler(Constants.CONSOLE_LOG_PATH, maxBytes=1000000, backupCount=10)
    #         # except Exception as e:
    #         #     handler_console = RotatingFileHandler(os.path.join("/tmp", log_console_filename), maxBytes=1000000, backupCount=10)
    #
    #         handler.setLevel(logging.DEBUG)
    #         formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    #         handler.setFormatter(formatter)
    #         app.logger.addHandler(handler)
    #
    #         #add stdout handler for screen out
    #         #stdout_handler = logging.StreamHandler(sys.stdout)
    #         #stdout_handler.setFormatter(formatter)
    #         #app.logger.addHandler(stdout_handler)
    #
    #         print("log initialized")
    #
    #         # log_console = logging.getLogger('werkzeug')
    #         # #log_console.setLevel(logging.DEBUG)
    #         # log_console.addHandler(handler_console)
    #         # log_console.addHandler(logging.StreamHandler(sys.stdout))
    #         # log_console.addHandler(logging.StreamHandler(sys.stderr))
    #     except Exception:
    #         raise Exception("Failed to start logging instance!")

    # set cli arguments
    @staticmethod
    def parse_arg():
        #global server_ip
        server_ip = HelperMethods.get_server_ip()
        parser = argparse.ArgumentParser(description="Gigagent Application")
        parser.add_argument('-m', action="store", dest="mode", type=str, default=Constants.RUN_MODE_THREAD)
        parser.add_argument('-i', action="store", dest="ip", type=str, default=server_ip)
        parser.add_argument('-p', action="store", dest="port", type=str, default=Constants.SERVER_PORT)
        parser.add_argument('-e', action="store", dest="env", type=str, default=Constants.ENV_PROD)
        return parser

    # set header no-cahce
    @staticmethod
    def set_no_cache(resp):
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0'
