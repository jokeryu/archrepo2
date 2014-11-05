#!/usr/bin/env python3

import tornado.ioloop
import tornado.web
import os
from archrepo2 import dbutil
import sqlite3
import pickle
import math
from datetime import date

settings = {
    'debug' : True,
    'gzip' : True, 
    'template_path': os.path.join(os.path.dirname(__file__), 'template'),
    'static_path': os.path.join(os.path.dirname(__file__), 'static'),
    'db_path': '',
    'page_size': '100',
}

def _execute(query):
    """Function to execute queries against a local sqlite database"""
    connection = sqlite3.connect(settings['db_path'])
    cursorobj = connection.cursor()
    try:
        cursorobj.execute(query)
        result = cursorobj.fetchall()
        connection.commit()
    except Exception:
        raise
    connection.close()
    return result

def _parseSort(sort):
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

    if (key in ['arch','pkgname','last_update']) == False:
        key = 'last_update'

    if key == 'arch':
        key = 'pkgarch'

    if key == 'last_update':
        key = 'mtime'

    return [key,order]

class PackagesHandle(tornado.web.RequestHandler):
    def get(self):
        try:
            page_cur = int(self.get_argument('page', 1))
        except Exception:
            page_cur = 1

        order = _parseSort(self.get_argument('sort', 'mtime').strip())
        order_str = ' '.join(order)
        if order[0] == 'pkgarch':
            order_str += ' , pkgname asc'

        limit = [str(int(settings['page_size']) * (page_cur - 1)), 
                 str(settings['page_size'])]
        where = 'pkgarch = forarch and state = 1'
        count = _execute('select count (*) from pkginfo where ' + where)[0][0]
        page_total = math.ceil(int(count) / int(settings['page_size']))

        pkgs = _execute('select mtime,info from pkginfo where ' + where + ' order by ' + order_str + ' limit ' + ','.join(limit))

        data_list = []
        for pkg in pkgs:
            info = pickle.loads(pkg[-1])
            info['mtime'] = date.fromtimestamp(int(pkg[0]))
            data_list.append(info)

        self.render("package_list.html", 
                    data_list = data_list, 
                    count = count, 
                    page_total = page_total,
                    page_cur = page_cur,
                    order = order,)

application = tornado.web.Application([
    (r"/", PackagesHandle),
], **settings)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()