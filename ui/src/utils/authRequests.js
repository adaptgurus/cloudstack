// Optional authentication discovery must not invalidate an active session.
export function isOptionalAuthenticationProbe (config = {}) {
  const body = typeof config.data === 'string' ? new URLSearchParams(config.data) : config.data
  const command = config.params?.command || body?.get?.('command')
  if (command === 'forgotPassword') {
    return !Object.prototype.hasOwnProperty.call(config.params || {}, 'username') && !body?.has?.('username')
  }
  return ['listIdps', 'cloudianIsEnabled'].includes(command)
}

export function isMissingLogoutSession (error) {
  return error?.response?.status === 431 && Object.values(error.response.data || {}).some(value =>
    value?.errortext === 'Session not found for the logout process.')
}
