import { shallowMount } from '@vue/test-utils'
import PageState from '@/components/page/LayerSentryPageState.vue'
import { layersentryPage, readFailure } from '@/config/layersentryPage'

const mountPage = props => shallowMount(PageState, {
  props: { title: 'Virtual Machines', ...props },
  global: {
    mocks: { $t: key => key, $toLocaleDate: value => value },
    stubs: {
      'a-alert': { template: '<aside><slot name="message" /><slot name="description" /></aside>' },
      'a-button': { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
      'a-tag': { template: '<span><slot /></span>' },
      'a-spin': true
    }
  }
})

describe('LayerSentry inventory read feedback', () => {
  it('keeps a disconnected request distinct from an empty inventory', () => {
    const failure = readFailure(new Error('Network Error'))
    const wrapper = mountPage({ failure, empty: true })
    expect(wrapper.text()).toContain('Network Error')
    expect(wrapper.text()).toContain('message.layersentry.read.failed')
    expect(wrapper.text()).not.toContain('label.layersentry.no.matches')
  })

  it('labels retained data stale and retries only on explicit action', async () => {
    const wrapper = mountPage({ failure: readFailure(new Error('Disconnected')), hasData: true })
    expect(wrapper.text()).toContain('message.layersentry.stale.data')
    expect(wrapper.emitted('retry')).toBeUndefined()
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    expect(wrapper.emitted('deploy')).toBeUndefined()
  })

  it('renders server diagnostics as text without exposing request configuration', () => {
    const failure = readFailure({
      config: { password: 'must-not-render' },
      response: { status: 431, data: { listvirtualmachinesresponse: { errorcode: 431, errortext: '<img src=x onerror=alert(1)>' } } }
    })
    const wrapper = mountPage({ failure })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
    expect(JSON.stringify(failure)).not.toContain('must-not-render')
  })

  it.each([401, 403, 405])('represents access denial %s without inventing absence', status => {
    expect(readFailure({ response: { status } }).status).toBe('forbidden')
  })

  it('bounds untrusted diagnostic length and ignores non-text objects', () => {
    expect(readFailure({ message: 'x'.repeat(8000) }).message).toHaveLength(2000)
    expect(readFailure({ message: { secret: 'no' } }).message).toBe('')
    expect(readFailure(null)).toEqual({ status: 'error', code: '', message: '', requestId: '' })
  })

  it('keeps loading separate from a confirmed empty response', () => {
    const wrapper = mountPage({ loading: true, empty: true })
    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).not.toContain('label.layersentry.no.matches')
  })

  it('provides a fallback identity without removing unfamiliar routes', () => {
    expect(layersentryPage('volume').section).toBe('storage')
    expect(layersentryPage('backup').section).toBe('backup')
    expect(layersentryPage('vendor-route').section).toBe('platform')
  })
})
