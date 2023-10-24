is.installed <- function(mypkg) is.element(mypkg, installed.packages()[,1])
if (is.installed("ggplot2") == FALSE){
    .libPaths( c( .libPaths(), "~/userLibrary") )
    install.packages("ggplot2", repos = "http://cran.r-project.org")
}

library(ggplot2)

if(file.exists("output/ipv8_overlay_stats.csv")){
    df <- read.csv("output/ipv8_overlay_stats.csv", sep=",", header=T)

    # Speed up
    p <- ggplot(df) + theme_bw()
    p <- p + geom_line(aes(x=time, y=num_peers, group=overlay_id, colour=overlay_id))
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Number of peers") + ggtitle("IPv8 Overlay Peer Statistics")
    p

    ggsave(file="output/ipv8_overlays.png", width=8, height=6, dpi=100)
}
