#!/usr/bin/env python

import os
import glob
import re
import datetime
import pickle
import subprocess
import numpy as np
import pandas as pd

def quarter_ceil(x): #{{{
    """ round up to nearest quarter """
    return np.ceil(x*4)/4. #}}}

def print_acmeanalysis(df): #{{{
    acmework = df[df['proj'].isin(['ACMEanalysis'])]\
                            .resample('W')\
                            .agg({'Measurement':'sum', 'Safe': lambda x: '; '.join(x.values)})
    for day, hrs, log in zip(acmework.index, acmework.Measurement.hrs, acmework.Safe.log):
        if not np.isnan(hrs):
            print 'Week of', day.date(), ':', log, "(%0.2f hrs)"%(quarter_ceil(hrs))
    return #}}}

def build_log(database): #{{{
    # get files organized in terms of year/month/day/daily.log
    logfiles = glob.glob(database + '/*/*/*/daily.log')

    tottimestamp = []
    totduration = []
    totproj = []
    tottask = []
    totlog = []
    totvalid = []
    for logfile in logfiles:
        # process raw data
        time = np.asarray([re.findall(r'..-..-.. ..:..:..', line)[0]  for line in open(logfile)])
        proj = np.asarray([re.findall(r'PROJ={.*?}', line)  for line in open(logfile)])
        task = np.asarray([re.findall(r'TASK={.*?}', line) for line in open(logfile)])
        log  = np.asarray([re.findall(r'LOG={.*?}', line) for line in open(logfile)])
        valid = [ap != [] for ap in proj]

        time = pd.to_datetime(time, format='%y-%m-%d %H:%M:%S')

        tottimestamp += time[:]
        totproj += proj.tolist()[:]
        tottask += task.tolist()[:]
        totlog  += log.tolist()[:]
        totvalid += valid[:]

    hours = np.asarray([0] + [atime.seconds/3600. for atime in np.diff(tottimestamp)])
    #plt.plot(tottimestamp,hours,'.'); plt.show()
    #assert hours[-1] < 3./60., 'Ending time is very large= ' + hours[-1]
    #assert proj[0] == [] and proj[-1] == [], "Don't necessarily have good data for " + logfile
    #assert task[0] == [] and task[-1] == [], "Don't necessarily have good data for " + logfile

    totproj = [item[0][6:-1] for item in np.asarray(totproj)[totvalid].tolist()]
    tottask = [item[0][6:-1] for item in np.asarray(tottask)[totvalid].tolist()]
    totlog  = [item[0][5:-1] for item in np.asarray(totlog)[totvalid].tolist()]
    totduration = np.asarray(hours)[totvalid]
    totstarttime = pd.to_datetime(np.asarray(tottimestamp)[totvalid])
    totendtime = totstarttime + pd.to_timedelta(totduration, unit='h')

    # build dataframe
    df = pd.DataFrame({ #'start' : totstarttime,
                         'end'   : totendtime,
                         'hrs' : totduration,
                         'proj' : totproj,
                         'task' : tottask,
                         'log' : totlog
                         }, index=pd.Series(totstarttime))
    # print summary
    print_acmeanalysis(df)

    #plt.plot(tottimestamp,totduration,'.'); plt.show()

    return #}}}

def folder_exists(folder, create=True, verbose=True): #{{{
    if not os.path.exists(folder):
        if create:
            print 'Creating folder at ', folder
            os.makedirs(folder)
        return False
    else:
        return True
    #}}}

def load_stored_sets(setlocation): #{{{
    if os.path.isfile(setlocation):
        with open(setlocation, 'r') as af:
            setvalues = pickle.load(af)
    else:
        setvalues = set()
    return setvalues #}}}

def save_stored_sets(aset, setlocation): #{{{
    print 'saving %s at %s'%(aset, setlocation)
    with open(setlocation, 'w') as af:
        pickle.dump(aset, af)
    return #}}}

def sanitize_response(response): #{{{
    # separate comma separated items
    values = response.split(',')
    # remove spaces in front or back of string
    values = [av.rstrip() for av in values]
    values = [av.lstrip() for av in values]
    return values #}}}

def make_log_entry(logfile, timestamp, projname, taskname, entry): #{{{
    with open(logfile, 'a') as lf:
        if entry == 'START' or entry == 'END':
            log = entry + '\n'
        else:
            log =  'PROJ={' + projname + '}, TASK={' + taskname + '}, LOG={' + entry + '}\n'
        line = timestamp + '\t '+ log
        lf.write(line)
        print 'wrote:\n   %s to\n%s'%(line, logfile)
    return #}}}

def undo_log_entry(logfile, timestamp): #{{{
    # remove last line
    with open(logfile, 'r+') as lf:
        lines = lf.readlines()
        lastline = lines[-1]
        lf.seek(0)
        for li in lines[:-1]:
            lf.write(li)
        lf.truncate()

    undofile = logfile + '.undo'
    with open(undofile, 'a') as lf:
        undoline = 'Undo at %s:'%(timestamp) + lastline
        lf.write(undoline)
        print 'wrote:\n   %s to\n%s'%(undoline, undofile)
    return #}}}

def file_locations(database): #{{{
    now = datetime.datetime.now()
    yearfolder = database + '/' + "%.4d"%(now.year)
    monthfolder = yearfolder + '/' + "%.2d"%(now.month)
    dayfolder = monthfolder + '/' + "%.2d"%(now.day)
    logfile = dayfolder + '/' + 'daily.log'
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    # make sure file locations are available
    for afold in [database, yearfolder, monthfolder, dayfolder]:
        folder_exists(afold)

    return logfile, timestamp #}}}

def print_items(prompt, items, nitems=3): #{{{
    # break items up into sets of 5
    print "================================================================================"
    print prompt
    print "--------------------------------------------------------------------------------"
    thelist = list(items)
    n = len(thelist)
    for i in np.arange(int(np.ceil(n/float(nitems)))):
        print thelist[nitems*i:(nitems*i+nitems)]
    print "================================================================================"
    return #}}}

def log_work(database, start, end, continued, undo): #{{{

    logfile, timestamp = file_locations(database)

    projectfile = database + '/projects.p'
    projects = load_stored_sets(projectfile)

    taskfile = database + '/tasks.p'
    tasks = load_stored_sets(taskfile)

    if undo:
        undo_log_entry(logfile, timestamp)
    elif start:
        make_log_entry(logfile, timestamp, '', '', 'START')
    elif end:
        make_log_entry(logfile, timestamp, '', '', 'END')
    elif continued:
        make_log_entry(logfile, timestamp, '', '', 'CONTINUED')
    else:
        print_items('Projects', sorted(projects))
        response = raw_input("Please enter project names, e.g., 'proj1, proj2, etc':\n")
        projname = sanitize_response(response)
        projects = projects | set(projname)

        print_items('Tasks', sorted(tasks))
        response = raw_input("Please enter task names, e.g., 'analysis, lit_review, misc':\n")
        taskname = sanitize_response(response)
        tasks = tasks | set(taskname)

        entry = raw_input("Please log entry:\n")
        # refresh time stamp to follow once entry is committed
        logfile, timestamp = file_locations(database)
        make_log_entry(logfile, timestamp, ','.join(projname), ','.join(taskname), entry)

        save_stored_sets(projects, projectfile)
        save_stored_sets(tasks, taskfile)
    return #}}}


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-d", "--database_location", dest="database", help="Location for work database", metavar="FOLDER")
    parser.add_option("-s", "--start", dest="start", help="Starting entry", action='store_true')
    parser.add_option("-e", "--end", dest="end", help="Ending entry", action='store_true')
    parser.add_option("-l", "--log", dest="log", help="Make analyzable log", action='store_true')
    parser.add_option("-c", "--continued", dest="continued", help="Continued entry", action='store_true')
    parser.add_option("-u", "--undo", dest="undo", help="Undo last entry", action='store_true')
    parser.add_option("-p", "--print", dest="printlog", help="Print daily work log", action='store_true')
    parser.add_option("-r", "--edit", dest="editlog", help="Edit daily work log", action='store_true')
    parser.set_defaults(start=False, end=False, undo=False, printlog=False)


    options, args = parser.parse_args()
    if not options.database:
        options.database = os.path.expanduser('~') + '/Documents/WorkLogDatabase'

    print "Using database at " + options.database

    if options.printlog:
        logfile, timestamp = file_locations(options.database)
        print "================================================================================"
        print 'Current time is %s'%(timestamp)
        print 'Outputing daily log %s:'%(logfile)
        print "--------------------------------------------------------------------------------"
        with open(logfile,'r') as lf:
            print lf.read()
            lf.close()
        print "--------------------------------------------------------------------------------"
        print logfile
    elif options.editlog:
        logfile, timestamp = file_locations(options.database)
        edit_call = [ "mvim", logfile]
        edit = subprocess.Popen(edit_call)
    elif options.log:
        # build the log database
        build_log(options.database)
    else:
        log_work(options.database, options.start, options.end, options.continued, options.undo)
