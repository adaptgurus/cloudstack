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

import {
  applyLayersentryNavigation,
  shouldHideLayersentrySection,
  withLayersentryKvmParams
} from '@/config/layersentryNavigation'

const profile = { productProfile: 'layersentry-kvm' }

describe('LayerSentry navigation presentation', () => {
  it('adds a KVM filter only to exact APIs that support the hypervisor parameter', () => {
    expect(withLayersentryKvmParams('vm', { details: 'min' }, profile)).toEqual({
      details: 'min',
      hypervisor: 'KVM'
    })
    expect(withLayersentryKvmParams('template', () => ({ templatefilter: 'self' }), profile)()).toEqual({
      templatefilter: 'self',
      hypervisor: 'KVM'
    })
    expect(withLayersentryKvmParams('volume', { listall: true }, profile)).toEqual({ listall: true })
  })

  it('leaves upstream profiles untouched', () => {
    expect(withLayersentryKvmParams('vm', { details: 'min' }, { productProfile: 'upstream' })).toEqual({ details: 'min' })
  })

  it('hides physical and platform configuration sections from normal users', () => {
    expect(shouldHideLayersentrySection('infra', { roletype: 'User' }, profile)).toBe(true)
    expect(shouldHideLayersentrySection('offering', { roletype: 'User' }, profile)).toBe(true)
    expect(shouldHideLayersentrySection('compute', { roletype: 'User' }, profile)).toBe(false)
    expect(shouldHideLayersentrySection('event', { roletype: 'User' }, profile)).toBe(false)
  })

  it('keeps department identity surfaces but hides physical infrastructure', () => {
    expect(shouldHideLayersentrySection('account', { roletype: 'DomainAdmin' }, profile)).toBe(false)
    expect(shouldHideLayersentrySection('domain', { roletype: 'DomainAdmin' }, profile)).toBe(false)
    expect(shouldHideLayersentrySection('infra', { roletype: 'DomainAdmin' }, profile)).toBe(true)
  })

  it('does not hide platform sections from Platform Administrators', () => {
    expect(shouldHideLayersentrySection('infra', { roletype: 'Admin' }, profile)).toBe(false)
    expect(shouldHideLayersentrySection('config', { roletype: 'Admin' }, profile)).toBe(false)
  })

  it('marks menu sections hidden without deleting direct routes or children', () => {
    const child = { name: 'host', path: '/host' }
    const routes = applyLayersentryNavigation([
      { name: 'infra', path: '/infra', children: [child] },
      { name: 'compute', path: '/compute' }
    ], { roletype: 'User' }, profile)
    expect(routes[0]).toEqual({ name: 'infra', path: '/infra', children: [child], hidden: true })
    expect(routes[1]).toEqual({ name: 'compute', path: '/compute' })
  })
})
