#!/bin/bash
set -x #echo on

curl https://s3-us-west-2.amazonaws.com/heroku-emacs/emacs-24.5-heroku-minimal.tar --location --silent | tar x
PATH=$PATH:/app/emacs/bin
export PATH

