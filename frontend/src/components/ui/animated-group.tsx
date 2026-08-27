'use client'

import React from 'react'
import { motion, type Variants } from 'framer-motion'
import { cn } from '@/lib/utils'

interface AnimatedGroupProps {
  children: React.ReactNode
  className?: string
  variants?: {
    container?: Variants
    item?: Variants
  }
}

const defaultContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const defaultItemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: 'spring',
      bounce: 0.3,
      duration: 1,
    },
  },
}

/**
 * AnimatedGroup — wraps children in a Framer Motion stagger container.
 * Each direct child gets wrapped in a motion.div with the item variants.
 *
 * Used in HeroSection to animate the headline, CTA buttons, and hero image
 * into view with a cascading spring entrance.
 */
export function AnimatedGroup({ children, className, variants }: AnimatedGroupProps) {
  const containerVariants = variants?.container ?? defaultContainerVariants
  const itemVariants = variants?.item ?? defaultItemVariants

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className={cn(className)}
    >
      {React.Children.map(children, (child, i) => (
        <motion.div key={i} variants={itemVariants}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  )
}
