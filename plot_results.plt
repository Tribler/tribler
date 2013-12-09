#!/usr/bin/gnuplot
# set terminal postscript eps enhanced colour size 10cm,8cm font 'Arial-Bold,14'
# set output 'plot.eps'

set term pngcairo
set output 'plot.png'

set title 'Download speed over circuits with different hop lengths'
set xlabel 'Number of hops'
set ylabel 'Speed [KB/s]'
set xtics 1

plot "hop_speed.txt" using 1:3  w lines title "Average speed [KB/s]"
