is.installed <- function(mypkg) is.element(mypkg, installed.packages()[,1])
if (is.installed("ggplot2") == FALSE){
    .libPaths( c( .libPaths(), "~/userLibrary") )
    install.packages("ggplot2", repos = "http://cran.r-project.org")
}

library(ggplot2)

if(file.exists("output/download_stats.csv")){
	df <- read.csv("output/download_stats.csv", sep=",", header=T)
	df$speed_up = df$speed_up / 1024
	df$speed_down = df$speed_down / 1024
    df$dl_progress = df$progress * 100

    # Speed up
    p <- ggplot(df) + theme_bw()
    p <- p + geom_line(aes(x=time, y=speed_up, group=infohash, colour=infohash))
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Upload speed (kb/s)") + ggtitle("Upload speed of downloads")
    p

    ggsave(file="output/speed_up.png", width=8, height=6, dpi=100)

    # Speed down
    p <- ggplot(df) + theme_bw()
    p <- p + geom_line(aes(x=time, y=speed_down, group=infohash, colour=infohash))
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Download speed (kb/s)") + ggtitle("Download speed of downloads")
    p

    ggsave(file="output/speed_down.png", width=8, height=6, dpi=100)

    # Progress
    p <- ggplot(df) + theme_bw()
    p <- p + geom_line(aes(x=time, y=dl_progress, group=infohash, colour=infohash))
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Progress (%)") + ylim(c(0, 100)) + ggtitle("Progress of downloads")
    p

    ggsave(file="output/progress.png", width=8, height=6, dpi=100)

    if(nrow(df) > 0) {
        # State
        df2 <- aggregate(df, by=list(df$time, df$status), FUN="length")
        p <- ggplot(df2, aes(x=Group.1, y=status, group=Group.2, colour=Group.2)) + theme_bw()
        p <- p + geom_line()
        p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Count") + ggtitle("Status of individual downloads")
        p <- p + guides(colour=guide_legend(ncol=3))
        p

        ggsave(file="output/download_states.png", width=8, height=6, dpi=100)
    }
}
