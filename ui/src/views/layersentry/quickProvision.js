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

function findOffering (offerings = [], id) {
  return offerings.find(offering => offering.id === id)
}

export function normaliseAdditionalNetworks (primaryNetworkId, additionalNetworkIds = []) {
  const seen = new Set()
  return (Array.isArray(additionalNetworkIds) ? additionalNetworkIds : [])
    .filter(Boolean)
    .filter(networkId => networkId !== primaryNetworkId)
    .filter(networkId => {
      if (seen.has(networkId)) return false
      seen.add(networkId)
      return true
    })
}

export function validateQuickProvisionRootStorage (form = {}, offerings = []) {
  const errors = []
  if (!form.rootdiskofferingid) {
    if (form.rootdisksize !== undefined && form.rootdisksize !== null && form.rootdisksize !== '') {
      const rootSize = Number(form.rootdisksize)
      if (!Number.isFinite(rootSize) || rootSize <= 0) errors.push('Root disk size must be a positive number.')
    }
    return errors
  }

  const offering = findOffering(offerings, form.rootdiskofferingid)
  if (!offering) {
    errors.push('The selected root Storage Profile is no longer available.')
    return errors
  }
  if (offering.iscustomizediops) {
    errors.push('Custom-IOPS root Storage Profiles require the advanced deployment workflow.')
  }
  if (offering.iscustomized) {
    const rootSize = Number(form.rootdisksize)
    if (!Number.isFinite(rootSize) || rootSize <= 0) {
      errors.push('The selected root Storage Profile requires a positive root disk size.')
    }
  } else if (form.rootdisksize !== undefined && form.rootdisksize !== null && form.rootdisksize !== '') {
    const rootSize = Number(form.rootdisksize)
    if (!Number.isFinite(rootSize) || rootSize <= 0) errors.push('Root disk size must be a positive number.')
  }
  return errors
}

export function validateQuickProvisionDataVolumes (volumes = [], offerings = []) {
  const errors = []
  ;(Array.isArray(volumes) ? volumes : []).forEach((volume, index) => {
    const number = index + 1
    if (!volume?.diskofferingid) {
      errors.push(`Data volume ${number} requires a Storage Profile.`)
      return
    }
    const offering = findOffering(offerings, volume.diskofferingid)
    if (!offering) {
      errors.push(`Data volume ${number} uses a Storage Profile that is no longer available.`)
      return
    }
    if (offering.iscustomized && (!Number.isFinite(Number(volume.size)) || Number(volume.size) <= 0)) {
      errors.push(`Data volume ${number} requires a positive size.`)
    }
    if (offering.iscustomizediops) {
      const minIops = Number(volume.miniops)
      const maxIops = Number(volume.maxiops)
      if (!Number.isFinite(minIops) || minIops < 0) {
        errors.push(`Data volume ${number} requires valid minimum IOPS.`)
      }
      if (!Number.isFinite(maxIops) || maxIops < minIops) {
        errors.push(`Data volume ${number} requires maximum IOPS greater than or equal to minimum IOPS.`)
      }
    }
  })
  return errors
}

export function buildQuickProvisionDeployParams ({
  form,
  networkType,
  storageProfiles = [],
  projectId
}) {
  const params = {
    name: form.name,
    displayname: form.name,
    zoneid: form.zoneid,
    templateid: form.templateid,
    serviceofferingid: form.serviceofferingid,
    hypervisor: 'KVM',
    startvm: form.startvm
  }

  if (projectId) params.projectid = projectId
  if (form.rootdiskofferingid) params.overridediskofferingid = form.rootdiskofferingid
  if (Number.isFinite(Number(form.rootdisksize)) && Number(form.rootdisksize) > 0) {
    params.rootdisksize = Number(form.rootdisksize)
  }

  const volumes = Array.isArray(form.dataVolumes) ? form.dataVolumes : []
  volumes.forEach((volume, index) => {
    const offering = findOffering(storageProfiles, volume.diskofferingid)
    if (!offering) return
    const prefix = `datadisksdetails[${index}]`
    params[`${prefix}.diskofferingid`] = volume.diskofferingid
    params[`${prefix}.deviceid`] = index + 1
    if (offering.iscustomized && Number.isFinite(Number(volume.size)) && Number(volume.size) > 0) {
      params[`${prefix}.size`] = Number(volume.size)
    }
    if (offering.iscustomizediops) {
      params[`${prefix}.miniops`] = Number(volume.miniops)
      params[`${prefix}.maxiops`] = Number(volume.maxiops)
    }
  })

  if (networkType !== 'Basic' && form.networkid) {
    const networks = [
      form.networkid,
      ...normaliseAdditionalNetworks(form.networkid, form.additionalnetworkids)
    ]
    networks.forEach((networkId, index) => {
      const prefix = `iptonetworklist[${index}]`
      params[`${prefix}.networkid`] = networkId
      if (index === 0 && form.ipaddress) params[`${prefix}.ip`] = form.ipaddress
    })
  }

  return params
}

export function quickProvisionBlockingIssues ({
  form,
  networkType,
  storageProfiles = [],
  kvmSiteReady = false,
  imageReady = false
}) {
  const issues = []
  if (!form.name) issues.push('Enter a VM name.')
  if (!form.zoneid) issues.push('Select a Site.')
  if (form.zoneid && !kvmSiteReady) issues.push('KVM availability for the Site is not verified.')
  if (!form.templateid) issues.push('Select an OS Image.')
  if (form.templateid && !imageReady) issues.push('The selected OS Image has not passed the KVM preflight.')
  if (!form.serviceofferingid) issues.push('Select a Compute Profile.')
  if (networkType !== 'Basic' && !form.networkid) issues.push('Select a Network Blueprint.')
  issues.push(...validateQuickProvisionRootStorage(form, storageProfiles))
  issues.push(...validateQuickProvisionDataVolumes(form.dataVolumes, storageProfiles))
  return issues
}
