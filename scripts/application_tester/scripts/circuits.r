is.installed <- function(mypkg) is.element(mypkg, installed.packages()[,1])
if (is.installed("ggplot2") == FALSE){
    .libPaths( c( .libPaths(), "~/userLibrary") )
    install.packages("ggplot2", repos = "http://cran.r-project.org")
}

library(ggplot2)
library(reshape2)

# Circuit states
if(file.exists("output/circuit_states.csv")){
	df <- read.csv("output/circuit_states.csv", sep=",", header=T)

	df <- melt(df, id.vars=c("time"), idvar="state")
	colnames(df)[2] = "state"

    p <- ggplot(df, aes(x=time, y=value, group=state, color=state)) + theme_bw()
    p <- p + geom_step()
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Total number of circuits") + ggtitle("Circuit states")
    p

    ggsave(file="output/circuit_states.png", width=8, height=6, dpi=100)
}

# Circuit types
if(file.exists("output/circuit_types.csv")){
	df <- read.csv("output/circuit_types.csv", sep=",", header=T)

	df <- melt(df, id.vars=c("time"), idvar="type")
	colnames(df)[2] = "type"

    p <- ggplot(df, aes(x=time, y=value, group=type, color=type)) + theme_bw()
    p <- p + geom_step()
    p <- p + theme(legend.position="bottom", legend.direction="horizontal") + xlab("Time into experiment (sec)") + ylab("Total number of circuits") + ggtitle("Circuit types")
    p

    ggsave(file="output/circuit_types.png", width=8, height=6, dpi=100)
}