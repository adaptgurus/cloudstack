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

import { filterProductImages } from './productProfile'

const profile = { productProfile: 'layersentry-kvm' }
const fail = key => { throw new Error(`message.layersentry.kvm.${key}`) }

export async function checkKvmSite (getAPI, zoneid) {
  if (!zoneid) fail('select.site')
  let response
  try {
    response = await getAPI('listHypervisors', { zoneid })
  } catch (error) {
    fail('lookup.failed')
  }
  const choices = response?.listhypervisorsresponse?.hypervisor
  if (!Array.isArray(choices)) {
    // CloudStack represents a successful empty list with an empty response object.
    if (response?.listhypervisorsresponse &&
        (Object.keys(response.listhypervisorsresponse).length === 0 || response.listhypervisorsresponse.count === 0)) fail('unavailable')
    fail('lookup.failed')
  }
  if (!choices.some(choice => choice?.name === 'KVM')) fail('unavailable')
  return [{ name: 'KVM' }]
}

async function readResource (getAPI, command, field, params) {
  let response
  try {
    response = await getAPI(command, params)
  } catch (error) {
    fail('image.lookup.failed')
  }
  const resources = response?.[command.toLowerCase() + 'response']?.[field]
  const resource = Array.isArray(resources) && resources.find(item => item.id === params.id)
  if (!resource) fail('image.invalid')
  return resource
}

export async function checkKvmImage (getAPI, zoneid, type, id, scope = {}) {
  if (!id) fail('image.invalid')
  const params = { ...scope, zoneid, id }
  if (type === 'templateid' || type === 'isoid') {
    const iso = type === 'isoid'
    const resource = await readResource(getAPI, iso ? 'listIsos' : 'listTemplates', iso ? 'iso' : 'template', {
      ...params,
      [iso ? 'isofilter' : 'templatefilter']: 'executable',
      isready: true,
      ...(iso ? { bootable: true } : { hypervisor: 'KVM' })
    })
    if (resource.isready !== true || (iso && resource.bootable !== true) ||
        (scope.forcks && resource.forcks !== true) ||
        filterProductImages([resource], iso, profile).length !== 1) fail('image.invalid')
    return
  }
  if (type === 'snapshotid') {
    const snapshot = await readResource(getAPI, 'listSnapshots', 'snapshot', params)
    if (snapshot.volumetype !== 'ROOT' || !snapshot.volumeid) fail('image.invalid')
    params.id = snapshot.volumeid
  } else if (type !== 'volumeid') {
    fail('image.invalid')
  }
  const volume = await readResource(getAPI, 'listVolumes', 'volume', params)
  if (volume.hypervisor !== 'KVM') fail('image.invalid')
}
