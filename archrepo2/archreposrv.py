#!/usr/bin/env python3

import os
import sys
import configparser
import logging
import math
import re
import sqlite3
import pickle
from datetime import date

from tornado.ioloop import IOLoop
from tornado.web import *

from .lib.nicelogger import enable_pretty_logging
enable_pretty_logging(logging.DEBUG)

from .repomon import repomon
from .repomon import dict_factory

logger = logging.getLogger(__name__)

def check_and_get_repos(config):
  repos = config['multi'].get('repos', 'repository')
  for field in ('name', 'path'):
    if config['multi'].get(field, None) is not None:
      raise ValueError('config %r cannot have default value.' % field)

  repos = {repo.strip() for repo in repos.split(',')}
  for field in ('name', 'path'):
    vals = [config[repo].get(field) for repo in repos]
    if len(vals) != len(set(vals)):
      raise ValueError('duplicate %s in different repositories.' % field)

  return repos

def _execute(db, query):
  conn = sqlite3.connect(db)
  conn.row_factory = dict_factory
  cursor = conn.cursor()
  cursor.execute(query)
  result = cursor.fetchall()
  conn.close()
  return result

def size_format(num, suffix='B'):
  for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
    if abs(num) < 1024.0:
      return "%3.1f%s%s" % (num, unit, suffix)
    num /= 1024.0
  return "%.1f%s%s" % (num, 'Yi', suffix)

def parse_sort(sort):
  try:
    if sort.startswith('-'):
      key = sort[1:]
      order = 'asc'
    else:
      key = sort
      order = 'desc'
  except Exception:
    order = 'desc'
    raise

  if key not in ('arch', 'pkgname', 'last_update'):
    key = 'last_update'

  if key == 'arch':
    key = 'pkgarch'

  if key == 'last_update':
    key = 'mtime'

  return [key, order]

class PackagesHandle(RequestHandler):
  def get(self):
    try:
      page_cur = int(self.get_argument('page', 1))
    except TypeError:
      page_cur = 1

    settings = self.application.settings;
    order = parse_sort(self.get_argument('sort', 'mtime').strip())
    order_str = ' '.join(order)
    if order[0] == 'pkgarch':
      order_str += ' , pkgname asc'

    limit = [str(int(settings['page_size']) * (page_cur - 1)),
             str(settings['page_size'])]
    where = ['pkgarch = forarch and state = 1']
    if self.get_argument('q', ''):
      where.append('and pkgname like "%%%s%%"' % self.get_argument('q'))
    if self.get_arguments('arch', []):
      where.append('and pkgarch in %s' % '("' + '","'.join(self.get_arguments('arch')) + '")')
    count = _execute(settings['db_path'], 'select count (*) as count '
                                          'from pkginfo '
                                          'where %s' % ' '.join(where))[0]['count']
    page_total = math.ceil(int(count) / int(settings['page_size']))

    pkgs = _execute(settings['db_path'],
                    'select mtime, info from pkginfo'
                    ' where %s'
                    ' order by %s'
                    ' limit %s'
                    % (' '.join(where), order_str, ','.join(limit)))
    data_list = []
    for pkg in pkgs:
      pkg['mtime'] = date.fromtimestamp(int(pkg['mtime']))
      data_list.append(pkg)

    self.render('package_list.html',
                data_list = data_list,
                count = count,
                page_total = page_total,
                page_cur = page_cur,
                order = order,
                q = self.get_argument('q', ''),
                arch = self.get_arguments('arch', []),)

class PackageInfoHandle(RequestHandler):
  def get(self, arch, pkgname):
    settings = self.application.settings;
    pkgname = pkgname.strip('/')

    info = _execute(settings['db_path'],
                    'select mtime, filename, info from pkginfo'
                    ' where pkgname = "%s"'
                    ' and forarch = "%s"'
                    ' and state = 1'
                    ' order by mtime desc limit 1'
                    % (pkgname, arch))[0]

    info['mtime'] = date.fromtimestamp(int(info['mtime']))
    info['builddate'] = date.fromtimestamp(int(info.get('builddate')))
    info['filesize'] = size_format(int(info.get('size')))
    pat = re.compile(r'<[^>]*>')
    info['packager'] = pat.sub('', info['packager'])
    info['download'] = 'http://repo.archlinuxcn.org/' + info['filename']
    self.render('package_info.html', info=info)

def main():
  conffile = sys.argv[1]
  config = configparser.ConfigParser(default_section='multi')
  config.read(conffile)
  repos = check_and_get_repos(config)

  notifiers = [repomon(config[repo]) for repo in repos]

  for repo in repos:
    webconfig = {
      'debug' : config[repo + '_web'].getboolean('debug', False),
      'template_path': os.path.join(os.path.dirname(__file__), 'template'),
      'static_path': os.path.join(os.path.dirname(__file__), 'static'),
      'page_size': config[repo + '_web'].getint('page-size', 100),
      'port': config[repo + '_web'].getint('port', 8888),
      'db_path': config[repo].get('info-db',
                 os.path.join(config[repo].get('path'), 'pkginfo.db'))
    }
    webservice = Application([
      (r"/", PackagesHandle),
      (r"/(any|x86_64|i686)/(.*)/?", PackageInfoHandle),
    ], **webconfig)
    webservice.listen(webconfig['port'])

  ioloop = IOLoop.instance()
  logger.info('starting archreposrv.')
  try:
    ioloop.start()
  except KeyboardInterrupt:
    ioloop.close()
    for notifier in notifiers:
      notifier.stop()
    print()

if __name__ == '__main__':
  if sys.version_info[:2] < (3, 3):
    raise OSError('Python 3.3+ required.')
  main()
