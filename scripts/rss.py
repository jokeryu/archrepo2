#!/usr/bin/env python3

import sys
from datetime import datetime
import sqlite3
import PyRSS2Gen
import pickle
from archrepo2 import dbutil

class MyRSS2(PyRSS2Gen.RSS2):
  PyRSS2Gen.RSS2.rss_attrs = {"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"}
  def publish_extensions(self, handler):
    PyRSS2Gen._element(handler, 'atom:link', None, {'href': 'http://repo.archlinux.cn', 'rel': 'self'})

def main():
  dbfile = sys.argv[1]
  rssfile = sys.argv[2]
  db = sqlite3.connect(dbfile)
  items = []
  latest = dbutil.latest(db, 50)

  for row in latest:
    info = pickle.loads(row[-1])
    items.append(PyRSS2Gen.RSSItem(
      title = info['pkgname']+' '+info['pkgver']+' '+info['arch'],
      link = info['url'],
      description = info['pkgdesc'],
      pubDate = datetime.fromtimestamp(row[3]),
      guid = PyRSS2Gen.Guid("http://repo.archlinux.cn", 0),
      categories = [info['arch']]
    ))
  rss = MyRSS2(
    title = "Arch Linux CN: Recent package updates",
    link = "http://repo.archlinux.cn",
    lastBuildDate = datetime.now(),
    items = items,
    generator = 'archrepo2',
    description = "Recently updated packages in the Arch Linux CN package repositories.",
  )
  rss.write_xml(open(rssfile, "w"), 'utf-8')

if __name__ == '__main__':
  main()