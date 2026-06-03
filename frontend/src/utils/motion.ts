export const softEntrance = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1 },
};

export const softItem = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: 8, scale: 0.98 },
};

export const softContainer = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.05,
    },
  },
};

export const entranceTransition = {
  duration: 0.5,
  ease: "easeOut" as const,
};

export const stateTransition = {
  duration: 0.3,
  ease: "easeInOut" as const,
};

export const softPress = {
  scale: 0.98,
};
