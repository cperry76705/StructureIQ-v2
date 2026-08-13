export const DEV_AUTH_EMAIL = 'dev@structureiq.local'
export const DEV_AUTH_PASSWORD = 'StructureIQ!Dev1'
export const DEV_AUTH_MFA = '123456'

export const isDevAuthEnabled = () => import.meta.env.VITE_ENABLE_DEV_AUTH === 'true'

export type DevAuthResult =
  | { ok: true; requiresMfa: true; mode: 'development' }
  | { ok: false; requiresMfa: false; reason: string }

export const validateDevCredentials = (email: string, password: string): DevAuthResult => {
  if (!isDevAuthEnabled()) {
    return {
      ok: false,
      requiresMfa: false,
      reason: 'Production authentication APIs are not connected. Enable VITE_ENABLE_DEV_AUTH=true only for local visual QA.',
    }
  }

  if (email === DEV_AUTH_EMAIL && password === DEV_AUTH_PASSWORD) {
    return { ok: true, requiresMfa: true, mode: 'development' }
  }

  return {
    ok: false,
    requiresMfa: false,
    reason: 'Invalid development credentials. Use the documented local visual-QA account.',
  }
}

export const validateDevMfa = (code: string) => {
  if (!isDevAuthEnabled()) {
    return {
      ok: false,
      reason: 'MFA verification requires production APIs unless local development auth is explicitly enabled.',
    }
  }
  return code === DEV_AUTH_MFA
    ? { ok: true, reason: 'Development MFA accepted.' }
    : { ok: false, reason: 'Invalid development MFA code.' }
}
