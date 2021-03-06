#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.

import time
import os
import re

from shinken.objects.item import Item, Items
from shinken.misc.perfdata import PerfDatas
from shinken.property import BoolProp, IntegerProp, FloatProp, CharProp, StringProp, ListProp
from shinken.log import logger

objs = {'hosts': [], 'services': []}
trigger_functions = {}


class declared(object):
    def __init__(self, f):
        self.f = f
        global functions
        n = f.func_name
        print "Adding the declared function", n, f
        trigger_functions[n] = f

    def __call__(self, *args):
        print "Calling", self.f.func_name, 'with', args
        return self.f(*args)


@declared
def critical(obj, output):
    logger.debug("[trigger::%s] I am in critical for object" % obj.get_name())
    now = time.time()
    cls = obj.__class__
    i = obj.launch_check(now, force=True)
    for chk in obj.actions:
        if chk.id == i:
            logger.debug("[trigger] I founded the check I want to change")
            c = chk
            # Now we 'transform the check into a result'
            # So exit_status, output and status is eaten by the host
            c.exit_status = 2
            c.get_outputs(output, obj.max_plugins_output_length)
            c.status = 'waitconsume'
            c.check_time = now
            #self.sched.nb_check_received += 1
            # Ok now this result will be read by scheduler the next loop


@declared
def set_value(obj_ref, output=None, perfdata=None, return_code=None):
    obj = get_object(obj_ref)
    if not obj:
        return
    output = output or obj.output
    perfdata = perfdata or obj.perfdata
    return_code = return_code or obj.state_id

    print "Will set", output, perfdata, return_code, "for the object", obj.get_full_name()

    if perfdata:
        output = output + ' | ' + perfdata

    now = time.time()
    cls = obj.__class__
    i = obj.launch_check(now, force=True)
    for chk in obj.actions:
        if chk.id == i:
            logger.debug("[trigger] I founded the check I want to change")
            c = chk
            # Now we 'transform the check into a result'
            # So exit_status, output and status is eaten by the host
            c.exit_status = return_code
            c.get_outputs(output, obj.max_plugins_output_length)
            c.status = 'waitconsume'
            c.check_time = now
            # IMPORTANT: tag this check as from a trigger, so we will not
            # loop in an infinite way for triggers checks!
            c.from_trigger = True
            # Ok now this result will be read by scheduler the next loop


@declared
def perf(obj_ref, metric_name):
    obj = get_object(obj_ref)
    p = PerfDatas(obj.perf_data)
    if metric_name in p:
        logger.debug("[trigger] I found the perfdata")
        return p[metric_name].value
    logger.debug("[trigger] I am in perf command")
    return 1


@declared
def get_custom(obj_ref, cname, default=None):
    obj = get_objects(obj_ref)
    if not obj:
        return default
    cname = cname.upper().strip()
    if not cname.startswith('_'):
        cname = '_' + cname
    return obj.customs.get(cname, default)


@declared
def perfs(objs_ref, metric_name):
    objs = get_objects(objs_ref)
    r = []
    for o in objs:
        v = perf(o, metric_name)
        r.append(v)
    return r


@declared
def get_object(ref):
    # Maybe it's already a real object, if so, return it :)
    if not isinstance(ref, basestring):
        return ref

    # Ok it's a string
    name = ref
    if not '/' in name:
        return objs['hosts'].find_by_name(name)
    else:
        elts = name.split('/', 1)
        return objs['services'].find_srv_by_name_and_hostname(elts[0], elts[1])


@declared
def get_objects(ref):
    # Maybe it's already a real object, if so, return it :)
    if not isinstance(ref, basestring):
        return ref

    name = ref
    # Maybe there is no '*'? if so, it's one element
    if not '*' in name:
        return get_object(name)

    # Ok we look for sliting the host or service thing
    hname = ''
    sdesc = ''
    if not '/' in name:
        hname = name
    else:
        elts = name.split('/', 1)
        hname = elts[0]
        sdesc = elts[1]
    print "Look for", hname, sdesc
    res = []
    hosts = []
    services = []

    # Look for host, and if need, look for service
    if not '*' in hname:
        h = objs['hosts'].find_by_name(hname)
        if h:
            hosts.append(h)
    else:
        hname = hname.replace('*', '.*')
        p = re.compile(hname)
        for h in objs['hosts']:
            print "Compare", hname, "with", h.get_name()
            if p.search(h.get_name()):
                hosts.append(h)

    # Maybe the user ask for justs hosts :)
    if not sdesc:
        return hosts

    for h in hosts:
        if not '*' in sdesc:
            s = h.find_service_by_name(sdesc)
            if s:
                services.append(s)
        else:
            sdesc = sdesc.replace('*', '.*')
            p = re.compile(sdesc)
            for s in h.services:
                print "Compare", s.service_description, "with", sdesc
                if p.search(s.service_description):
                    services.append(s)

    print "Found services", services
    return services
