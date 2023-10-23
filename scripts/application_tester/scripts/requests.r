is.installed <- function(mypkg) is.element(mypkg, installed.packages()[,1])
if (is.installed("ggplot2") == FALSE){
    install.packages("ggplot2", repos = "http://cran.r-project.org")
}

library(ggplot2)

if(file.exists("output/request_times.csv")){
	df <- read.csv("output/request_times.csv", sep=",", header=T)
    df$start_time <- df$start_time / 1000.0

    # Boxplot
    p <- ggplot(df, aes(x=request_type, y=duration, fill=request_type)) + theme_bw()
    p <- p + geom_boxplot()
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Request endpoint") + ylab("Request duration (ms)") + ggtitle("Duration of various requests")
    p <- p + coord_flip()
    p

    ggsave(file="output/request_times_boxplot.png", width=8, height=6, dpi=100)

    # Plotting the durations over time
    p <- ggplot(df, aes(x=start_time, y=duration, group=request_type, colour=request_type)) + theme_bw()
    p <- p + geom_line()
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time since start (s.)") + ylab("Request duration (ms)") + ggtitle("Duration of various requests")
    p

    ggsave(file="output/request_times.png", width=8, height=6, dpi=100)
}
