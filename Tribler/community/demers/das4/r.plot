library(ggplot2)
library(reshape)
#library(pracma)

summarySE <- function(data=NULL, measurevar, groupvars=NULL, na.rm=FALSE,
                      conf.interval=.95, .drop=TRUE) {
    require(plyr)

    # New version of length which can handle NA's: if na.rm==T, don't count them
    length2 <- function (x, na.rm=FALSE) {
        if (na.rm) sum(!is.na(x))
        else       length(x)
    }

    # This is does the summary; it's not easy to understand...
    datac <- ddply(data, groupvars, .drop=.drop,
                   .fun= function(xx, col, na.rm) {
                           c( N    = length2(xx[,col], na.rm=na.rm),
                              mean = mean   (xx[,col], na.rm=na.rm),
                              sd   = sd     (xx[,col], na.rm=na.rm)
                              )
                          },
                    measurevar,
                    na.rm
             )

    # Rename the "mean" column    
    datac <- rename(datac, c("mean"=measurevar))

    datac$se <- datac$sd / sqrt(datac$N)  # Calculate standard error of the mean

    # Confidence interval multiplier for standard error
    # Calculate t-statistic for confidence interval: 
    # e.g., if conf.interval is .95, use .975 (above/below), and use df=N-1
    ciMult <- qt(conf.interval/2 + .5, datac$N-1)
    datac$ci <- datac$se * ciMult

    return(datac)
}
propFUN2 <- function(row){
	c <- as.integer(row['x']) / 5.0
	initial <- as.integer(row['push'])
	ans <- propFUN(initial, c)
	ans <- 1 - ans
	print(paste(ans, initial, c, sep=","))
	
	ans
}
propFUN <- function(initial, x){
	if (x == 0){
		ans <- (1000 - initial - 1)/1000.0
	}else{
		prevCycle <- propFUN(initial, x - 1)
		ans <- prevCycle ^ 2
	}
	ans
}

d10 <- read.table("received_records_10.txt", header = FALSE)
colnames(d10) <- c("nrpeers", "cycle", "part")
d10$nrpeers <- d10$nrpeers / max(d10$nrpeers)
d10$type = "Push 10"

df <- summarySE(d10, "cycle", groupvars = c("nrpeers", "type"))

#dfz <- data.frame(x=seq(5,max(df10$cycle),5), type = "Push 10")
#dfz$z <- with(df10, interp1(cycle, nrpeers, df10z$x))

prop <- data.frame(x=seq(0,70,5))
prop$push <- 10
prop$type <- "Prob 10"
prop$val <- apply(prop, 1, propFUN2)

p <- ggplot() + theme_bw()
p <- p + geom_line(data = df, aes(x=cycle, y=nrpeers, group=type, colour=type))
p <- p + geom_line(data = prop, aes(x = x, y = val, colour=type, group=type), linetype="dashed")
#p <- p + geom_point(data = dfz, aes(x = x, y=z, shape=type, colour=type))
#p <- p + geom_point(data = prop, aes(x = x, y = val, shape=type, colour=type))
#p <- p + geom_errorbar(data = dfc, aes(x=cycle, ymin=yMin, ymax=yMax), width=.1)
#p <- p + opts(legend.position="bottom", legend.direction="horizontal")
p <- p + scale_colour_brewer(palette="Dark2", name="", breaks= c("Push 10","Prob 10"), labels = c("Emulation 11     ",  "Demers 11"))
p <- p + scale_shape(name="", breaks= c("Push 10","Prob 10"), labels = c("Emulation 11     ", "Demers 11"))
#p <- p + opts(axis.text.x = theme_text(colour = "grey50"), axis.text.y = theme_text(colour = "grey50"))
p <- p + opts(legend.position="bottom", legend.direction="horizontal")
p <- p + scale_x_continuous(breaks=seq(0, 70, 5))
p <- p + labs(y = "Probability of nodes\nhaving received the bundle", x = "Time since bundle was created (seconds)")
p

ggsave(file="demers_histogram.png", width=8, height=6, dpi=100)