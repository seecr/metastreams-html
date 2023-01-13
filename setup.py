## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2008-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013, 2015, 2022 Seecr (Seek You Too B.V.) https://seecr.nl
#
# This file is part of "Metastreams Html"
#
# "Metastreams Html" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Metastreams Html" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Metastreams Html"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from setuptools import setup, find_packages

packages=find_packages(exclude=('metastreams',))
packages=find_packages() #DO_NOT_DISTRIBUTE

setup(
    name='metastreams-html',
    packages=packages,
    package_data={
        'metastreams.html': ['templates/*.sf'],
    },
    scripts=['bin/metastreams-html-server'],
    version='%VERSION%',
    author='Seecr (Seek You Too B.V.)',
    author_email='info@seecr.nl',
    description='Metastreams Html is a template engine based on generators and a sequel to Slowfoot',
    long_description='Metastreams Html is a template engine based on generators and a sequel to Slowfoot. It is also known as "DynamicHtml" or "Seecr Html"',
    license='GNU Public License',
    platforms='all',
)
