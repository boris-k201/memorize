#!/bin/bash

for i in $(ls *.ui); do pyside6-uic "$i" -o ui_`echo "$i" | head -c -4`.py; done
