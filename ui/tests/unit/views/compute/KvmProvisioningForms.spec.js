// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied. See the License for the
// specific language governing permissions and limitations
// under the License.

import fs from 'fs'
import path from 'path'
import * as guards from '@/config/kvmProvisioning'
import * as profile from '@/config/productProfile'

jest.mock('@/vue-app', () => ({ vueProps: { $config: { productProfile: 'layersentry-kvm' } } }))

// Execute the actual SFC methods with controlled API dependencies. This tests the
// mutation boundary and races, not rendering; browser acceptance is separate.
function componentMethods (name, api) {
  const source = fs.readFileSync(path.join(__dirname, '../../../../src/views/compute', name + '.vue'), 'utf8')
    .split('<script>')[1].split('</script>')[0]
  const names = []
  const values = []
  const dependencies = { ...guards, ...profile, ...api, toRaw: value => value }
  const script = source.replace(/^import (.+) from '[^']+'\s*$/gm, (_, bindings) => {
    for (const binding of bindings.replace(/[{}]/g, '').split(',')) {
      const name = binding.trim()
      names.push(name)
      values.push(dependencies[name] || {})
    }
    return ''
  }).replace('export default', 'return')
  return new Function(...names, script)(...values).methods // eslint-disable-line no-new-func
}

const capability = names => ({ listhypervisorsresponse: { hypervisor: names.map(name => ({ name })) } })
const template = hypervisor => ({ listtemplatesresponse: { template: [{ id: 'image-a', hypervisor, isready: true, forcks: true }] } })

function context () {
  return {
    kvmProfile: true,
    kvmRequest: 0,
    kvmStatus: '',
    $t: key => key,
    $notification: { error: jest.fn() },
    $notifyError: jest.fn(),
    $pollJob: jest.fn(),
    $router: { back: jest.fn() },
    formRef: { value: { validate: () => Promise.resolve(), scrollToField: jest.fn() } }
  }
}

function vmContext (methods) {
  return {
    ...context(),
    ...methods,
    loading: { deploy: false },
    options: {},
    form: { zoneid: 'site-a', templateid: 'image-a', computeofferingid: 'offering-a' },
    imageType: 'templateid',
    template: {},
    serviceOffering: {},
    zone: { networktype: 'Basic' },
    owner: {},
    securitygroupids: [],
    sshKeyPairs: []
  }
}

function cksContext (methods) {
  return {
    ...context(),
    ...methods,
    loading: false,
    form: { zoneid: 0, kubernetesversionid: 0, serviceofferingid: 0, hypervisor: null },
    selectedZone: { id: 'site-a' },
    zones: [{ id: 'site-a' }],
    kubernetesVersions: [{ id: 'version-a' }],
    serviceOfferings: [{ id: 'offering-a' }],
    templates: [{ id: 'image-a', hypervisor: 'KVM' }],
    selectedZoneHypervisors: [],
    handleRemoveFields: value => ({ ...value }),
    closeAction: jest.fn()
  }
}

describe('KVM form mutation boundaries', () => {
  beforeEach(() => jest.useFakeTimers())
  afterEach(() => jest.useRealTimers())

  it.each(['DeployVM', 'CreateKubernetesCluster'])('%s does not let a previous Site response restore KVM', async name => {
    let resolveOld
    const getAPI = jest.fn()
      .mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
      .mockResolvedValueOnce(capability(['VMware']))
    const methods = componentMethods(name, { getAPI })
    const vm = name === 'DeployVM' ? vmContext(methods) : cksContext(methods)
    const first = vm.fetchKvmHypervisors()
    vm.form.zoneid = 'site-b'
    vm.selectedZone = { id: 'site-b' }
    await vm.fetchKvmHypervisors()
    resolveOld(capability(['KVM']))
    await first
    expect(vm.kvmStatus).toBe('message.layersentry.kvm.unavailable')
    expect(vm.form.hypervisor).toBeNull()
  })

  it.each(['VMware', undefined])('blocks VM submit when the selected template reports %s', async hypervisor => {
    const getAPI = jest.fn().mockResolvedValueOnce(capability(['KVM'])).mockResolvedValueOnce(template(hypervisor))
    const postAPI = jest.fn()
    const vm = vmContext(componentMethods('DeployVM', { getAPI, postAPI }))
    await vm.handleSubmit()
    expect(postAPI).not.toHaveBeenCalled()
    expect(vm.loading.deploy).toBe(false)
    expect(vm.kvmStatus).toBe('message.layersentry.kvm.image.invalid')
  })

  it('sends a native VM KVM deployment after rechecking the Site and image', async () => {
    const getAPI = jest.fn().mockResolvedValueOnce(capability(['KVM'])).mockResolvedValueOnce(template('KVM'))
    const postAPI = jest.fn().mockResolvedValue({ deployvirtualmachineresponse: {} })
    const vm = vmContext(componentMethods('DeployVM', { getAPI, postAPI }))
    await vm.handleSubmit()
    expect(postAPI).toHaveBeenCalledWith('deployVirtualMachine', expect.objectContaining({ zoneid: 'site-a', templateid: 'image-a', hypervisor: 'KVM' }))
  })

  it('blocks a changed VM selection while the submit check is pending', async () => {
    let resolveSite
    const getAPI = jest.fn().mockImplementationOnce(() => new Promise(resolve => { resolveSite = resolve })).mockResolvedValueOnce(template('KVM'))
    const postAPI = jest.fn()
    const vm = vmContext(componentMethods('DeployVM', { getAPI, postAPI }))
    const submission = vm.handleSubmit()
    await Promise.resolve()
    vm.form.zoneid = 'site-b'
    resolveSite(capability(['KVM']))
    await submission
    expect(postAPI).not.toHaveBeenCalled()
    expect(vm.kvmStatus).toBe('message.layersentry.kvm.selection.changed')
  })

  it.each(['DeployVM', 'CreateKubernetesCluster'])('%s submits once when two validation callbacks complete together', async name => {
    const getAPI = jest.fn().mockResolvedValueOnce(capability(['KVM'])).mockResolvedValueOnce(template('KVM'))
    const postAPI = jest.fn().mockResolvedValue({ deployvirtualmachineresponse: {}, createkubernetesclusterresponse: {} })
    const methods = componentMethods(name, { getAPI, postAPI })
    const vm = name === 'DeployVM' ? vmContext(methods) : cksContext(methods)
    await Promise.all([vm.handleSubmit(), vm.handleSubmit()])
    expect(postAPI).toHaveBeenCalledTimes(1)
  })

  it('makes native CKS KVM explicit even when the form hypervisor is unset', async () => {
    const getAPI = jest.fn().mockResolvedValue(capability(['VMware', 'KVM']))
    const postAPI = jest.fn().mockResolvedValue({ createkubernetesclusterresponse: { jobid: 'job-a' } })
    const vm = cksContext(componentMethods('CreateKubernetesCluster', { getAPI, postAPI }))
    await vm.handleSubmit()
    expect(postAPI).toHaveBeenCalledWith('createKubernetesCluster', expect.objectContaining({ zoneid: 'site-a', hypervisor: 'kvm', clustertype: 'CloudManaged' }))
  })

  it('blocks native CKS when the Site lookup fails', async () => {
    const getAPI = jest.fn().mockRejectedValue(new Error('denied'))
    const postAPI = jest.fn()
    const vm = cksContext(componentMethods('CreateKubernetesCluster', { getAPI, postAPI }))
    await vm.handleSubmit()
    expect(postAPI).not.toHaveBeenCalled()
    expect(vm.loading).toBe(false)
    expect(vm.kvmStatus).toBe('message.layersentry.kvm.lookup.failed')
  })

  it('rechecks native CKS custom node image IDs before submitting', async () => {
    const getAPI = jest.fn().mockResolvedValueOnce(capability(['KVM'])).mockResolvedValueOnce(template('VMware'))
    const postAPI = jest.fn()
    const vm = cksContext(componentMethods('CreateKubernetesCluster', { getAPI, postAPI }))
    Object.assign(vm.form, { advancedmode: true, controltemplateid: 0 })
    await vm.handleSubmit()
    expect(postAPI).not.toHaveBeenCalled()
    expect(vm.kvmStatus).toBe('message.layersentry.kvm.image.invalid')
  })

  it.each(['DeployVM', 'CreateKubernetesCluster'])('%s retains upstream submit behavior outside the profile', async name => {
    const getAPI = jest.fn()
    const postAPI = jest.fn().mockResolvedValue({ deployvirtualmachineresponse: {}, createkubernetesclusterresponse: {} })
    const methods = componentMethods(name, { getAPI, postAPI })
    const vm = name === 'DeployVM' ? vmContext(methods) : cksContext(methods)
    vm.kvmProfile = false
    await vm.handleSubmit()
    expect(getAPI).not.toHaveBeenCalled()
    expect(postAPI).toHaveBeenCalledTimes(1)
    expect(postAPI.mock.calls[0][1]).not.toHaveProperty('hypervisor')
  })
})
