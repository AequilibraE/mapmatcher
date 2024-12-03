# -*- coding: utf-8 -*-


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
from datetime import datetime
from pathlib import Path

project_dir = Path(__file__).parent.parent.parent
if str(project_dir) not in sys.path:
    sys.path.append(str(project_dir))

# Sometimes this file is exec'd directly from sphinx code...
project_dir = os.path.abspath("../../")
if str(project_dir) not in sys.path:
    sys.path.insert(0, project_dir)

from mapmatcher import __version__ as version

# -- Project information -----------------------------------------------------

project = "mapmatcher"
copyright = f"{str(datetime.now().date())}, MapMatcher developers"
author = "Pedro Camargo"


# -- General configuration ---------------------------------------------------
# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_gallery.gen_gallery",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.autosummary",
    "sphinx.ext.githubpages",
]

# myst_enable_extensions = ["html_admonition", "colon_fence"]

sphinx_gallery_conf = {
    "examples_dirs": "examples",  # path to your example scripts
    "gallery_dirs": "_auto_examples",  # path to where to save gallery generated output
    "capture_repr": ("_repr_html_", "__repr__"),
    "remove_config_comments": True,
}

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = [".rst"]

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "_auto_examples/**/*.ipynb"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = "pyramid"
html_theme = "pydata_sphinx_theme"
html_title = "MapMatcher"
html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/AequilibraE/mapmatcher",
            "icon": "fa-brands fa-github",
        }
    ]
}
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ["_static"]

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "mapmatcher"

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "mapmatcher.tex",
        "mapmatcher Documentation",
        "Pedro Camargo",
        "manual",
    )
]

pdf_documents = [(master_doc, "mapmatcher.pdf", "mapmatcher Documentation", "Pedro Camargo")]

# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "mapmatcher", "mapmatcher Documentation", [author], 1)]

# -- Options for Texinfo output ----------------------------------------------

autodoc_default_options = {
    "members": "var1, var2",
    "member-order": "bysource",
    "special-members": "__init__",
    "private-members": False,
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "inherited-members": False,
    "show-inheritance": False,
    "autodoc_inherit_docstrings": False,
}

autodoc_member_order = "groupwise"

autoclass_content = "class"  # classes should include both the class' and the __init__ method's docstring

autosummary_generate = True

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "mapmatcher",
        "mapmatcher Documentation",
        author,
        "mapmatcher",
        "mapmatcher.",
        "Miscellaneous",
    )
]
