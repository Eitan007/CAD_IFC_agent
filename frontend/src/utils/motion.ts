/** Shared motion language: soft, cinematic, and deliberately restrained. */
export const motionPresets = {
  page: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 20 },
    transition: { duration: 0.5, ease: "easeOut" as const },
  },
  contentSwap: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
    transition: { duration: 0.4 },
  },
  modal: {
    initial: { opacity: 0, scale: 0.95, y: 16 },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: 12 },
    transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] as const },
  },
  success: {
    initial: { scale: 0 },
    animate: { scale: 1 },
    transition: { type: "spring" as const, stiffness: 300, damping: 18 },
  },
};

export const softEntrance = {
  hidden: motionPresets.page.initial,
  show: motionPresets.page.animate,
  exit: motionPresets.page.exit,
};

export const softItem = {
  hidden: motionPresets.contentSwap.initial,
  show: motionPresets.contentSwap.animate,
  exit: motionPresets.contentSwap.exit,
};

export const softContainer = {
  hidden: { opacity: 0, y: 20, backdropFilter: "blur(0px)" },
  show: {
    opacity: 1,
    y: 0,
    backdropFilter: "blur(10px)",
    transition: {
      duration: 2,
      ease: "easeOut" as const,
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
  y: 0,
  scale: 0.98,
};
