import { login, oauthlogin } from '@/api'
import { axios, sourceToken } from '@/utils/request'
import { isOptionalAuthenticationProbe } from '@/utils/authRequests'

jest.mock('@/utils/request', () => ({
  axios: jest.fn(),
  sourceToken: { checkExistSource: jest.fn(() => true), init: jest.fn() }
}))
jest.mock('@/vue-app', () => ({ vueProps: { $localStorage: { get: jest.fn() } } }))
jest.mock('js-cookie', () => ({ get: jest.fn() }))
jest.mock('ant-design-vue', () => ({ message: {}, notification: {} }))

const noSession = { response: { status: 431, data: { errorresponse: { errortext: 'Session not found for the logout process.' } } } }

describe('authentication request ordering', () => {
  beforeEach(() => jest.clearAllMocks())

  it.each([login, oauthlogin])('waits for old session cleanup before sending credentials', async authenticate => {
    let finishLogout
    axios.mockImplementationOnce(() => new Promise(resolve => { finishLogout = resolve }))
      .mockResolvedValueOnce({ loginresponse: { userid: 'test-user' } })
    const result = authenticate({ username: 'test', password: 'unused' })
    expect(axios).toHaveBeenCalledTimes(1)
    expect(axios.mock.calls[0][0].data.get('command')).toBe('logout')
    finishLogout({ logoutresponse: { description: 'success' } })
    await result
    expect(axios).toHaveBeenCalledTimes(2)
    expect(['login', 'oauthlogin']).toContain(axios.mock.calls[1][0].data.get('command'))
  })

  it('accepts only the native already-absent-session result', async () => {
    axios.mockRejectedValueOnce(noSession).mockResolvedValueOnce({ loginresponse: {} })
    await expect(login({ username: 'test', password: 'unused' })).resolves.toEqual({ loginresponse: {} })
  })

  it.each([
    { response: { status: 431, data: { errorresponse: { errortext: 'Different parameter error' } } } },
    { response: { status: 500 } },
    new Error('network failure')
  ])('does not send login after an unresolved logout failure', async error => {
    axios.mockRejectedValueOnce(error)
    await expect(login({ username: 'test', password: 'unused' })).rejects.toBe(error)
    expect(axios).toHaveBeenCalledTimes(1)
  })

  it('initializes a missing cancellation source', async () => {
    sourceToken.checkExistSource.mockReturnValueOnce(false)
    axios.mockResolvedValue({})
    await login({ username: 'test', password: 'unused' })
    expect(sourceToken.init).toHaveBeenCalledTimes(1)
  })
})

describe('optional authentication discovery', () => {
  it.each([
    { params: { command: 'forgotPassword' } },
    { data: new URLSearchParams({ command: 'forgotPassword' }) },
    { data: 'command=forgotPassword&response=json' },
    { params: { command: 'listIdps' } }
  ])('recognizes capability discovery without logging out', config => {
    expect(isOptionalAuthenticationProbe(config)).toBe(true)
  })

  it.each([
    { params: { command: 'forgotPassword', username: 'test' } },
    { data: 'command=forgotPassword&username=' },
    { params: { command: 'forgotPassword' }, data: 'username=test' },
    { params: { command: 'listVirtualMachines' } }
  ])('keeps real requests subject to authorization failure handling', config => {
    expect(isOptionalAuthenticationProbe(config)).toBe(false)
  })
})
