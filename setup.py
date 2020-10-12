#!/usr/bin/env python3

import os, re
from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))


with open(os.path.join(here, 'README.md')) as f:
    README = f.read()

if __name__ == "__main__":
    setup(
        name = 'django-tsunami',
        # Version comes from git
        setup_requires = ['setuptools_scm'],
        use_scm_version = True,
        description = 'Events and controlled actions for Django.',
        long_description = README,
        classifiers = [
            "Programming Language :: Python",
            "Framework :: Django",
        ],
        author = 'Matt Pryor',
        author_email = 'matt.pryor@stfc.ac.uk',
        url = 'https://github.com/mkjpryor-stfc/django-tsunami',
        keywords = 'web django event action',
        packages = find_packages(exclude = ["tests"]),
        include_package_data = True,
        zip_safe = False,
        install_requires = [
            'django',
            'django-admin-list-filter-dropdown',
            'django-admin-rangefilter',
            'django-settings-object',
            'jsonfield',
        ],
    )
