library(ggplot2)
library(reshape2)

hidden_peer_discovery <- read.table("hidden_peer_discovery.txt", header=T, quote="\"")
hidden_peer_discovery <- hidden_peer_discovery[c(1:5)]
hidden_peer_discovery <- melt(hidden_peer_discovery , id.vars = 'Time', variable.name = 'Items')
p <- ggplot(hidden_peer_discovery, aes(Time, value)) +
  geom_line(aes(colour = Items)) +
  ggtitle("Hidden swarm peer discovery") + 
  ylab("") +
  xlab("Time (s)") +
  facet_grid(Items ~ .) +
  theme(legend.title=element_blank())
p
ggsave("hidden_peer_discovery.png", width=10, height=6, dpi=100)
q(save="no")
