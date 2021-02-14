library(ggplot2)
library(reshape2)

speed_test_exit <- read.table("speed_test_e2e.txt", header=T, quote="\"")

upload_speeds <- subset(speed_test_exit, Type == 1)
p <- ggplot(upload_speeds, aes(x=Time, y=Speed, colour=factor(Circuit), group=Circuit)) +
    geom_line() +
    scale_colour_discrete(name="Circuit") +
	stat_summary(aes(colour="mean", group=1), fun=mean, geom="line", size=1.1) +
	scale_y_continuous(name="Speed (KiB/s)") +
    ggtitle("Upload speed for e2e circuits")
p
ggsave("speed_test_e2e_upload.png", width=10, height=6, dpi=100)

download_speeds <- subset(speed_test_exit, Type == 0)
p <- ggplot(download_speeds, aes(x=Time, y=Speed, colour=factor(Circuit), group=Circuit)) +
    geom_line() +
    scale_colour_discrete(name="Circuit") +
	stat_summary(aes(colour="mean", group=1), fun=mean, geom="line", size=1.1) +
	scale_y_continuous(name="Speed (KiB/s)") +
    ggtitle("Download speed for e2e circuits")
p
ggsave("speed_test_e2e_download.png", width=10, height=6, dpi=100)
q(save="no")
