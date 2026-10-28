'use client'

import { createContext, useContext } from 'react'

export const ProgramDialogState = createContext({ busy: false, change: (_delta: number) => {} })
export const useProgramDialogState = () => useContext(ProgramDialogState)
