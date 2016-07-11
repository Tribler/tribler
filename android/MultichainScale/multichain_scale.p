set terminal svg size 1920,1080 fname 'Arial' fsize 14
set output 'multichain_scale.svg'
set xrange [0:1500]
set yrange [0:11000]
set xtic auto
set ytic auto
set title "Generation of multichain blocks"
set xlabel "Time (seconds)"
set ylabel "Number of created blocks"

plot "pc-pim-[#2175].dat" using 2:1 title 'PC' with linespoints, \
     "galaxy-S6-edge-[#2175].dat" using 2:1 title 'S6 edge' with linespoints, \
     "nexus-6-[?].dat" using 2:1 title 'Nexus 6' with linespoints, \
     "nexus-5-[#2175].dat" using 2:1 title 'Nexus 5' with linespoints, \
     "galaxy-S3-[#2175].dat" using 2:1 title 'S3' with linespoints, \
     "nexus-6-[#2452].dat" using 1:2 title 'Nexus 6' with linespoints, \
     "nexus-6-[#2452]-2.dat" using 1:2 title 'Nexus 6' with linespoints, \
     "galaxy-S3-[#2452].dat" using 1:2 title 'S3' with linespoints, \
     "galaxy-S3-[#2452]-2.dat" using 1:2 title 'S3' with linespoints

unset output
