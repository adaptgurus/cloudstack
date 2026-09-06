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

const ADMIN_OWNERSHIP_ROLES = new Set(['Admin', 'DomainAdmin'])

export const QUICK_PROVISION_SCOPE_MODES = Object.freeze({
  CURRENT: 'current',
  DEPARTMENT: 'department',
  PROJECT: 'project'
})

function findOffering (offerings = [], id) {
  return offerings.find(offering => offering.id === id)
}

function isPositiveNumber (value) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0
}

function isPositiveInteger (value) {
  const number = Number(value)
  return Number.isInteger(number) && number > 0
}

export function canChooseQuickProvisionOwnership (roleType) {
  return ADMIN_OWNERSHIP_ROLES.has(roleType)
}

export function buildQuickProvisionScopeParams ({
  form = {},
  currentProjectId,
  roleType
} = {}) {
  if (!canChooseQuickProvisionOwnership(roleType)) {
    return currentProjectId ? { projectid: currentProjectId } : {}
  }

  const mode = form.scopeMode || QUICK_PROVISION_SCOPE_MODES.CURRENT
  if (mode === QUICK_PROVISION_SCOPE_MODES.PROJECT) {
    return form.targetprojectid ? { projectid: form.targetprojectid } : {}
  }
  if (mode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) {
    if (!form.targetdomainid || !form.targetaccount) return {}
    return {
      domainid: form.targetdomainid,
      account: form.targetaccount
    }
  }
  return currentProjectId ? { projectid: currentProjectId } : {}
}

export function validateQuickProvisionOwnership ({
  form = {},
  roleType
} = {}) {
  if (!canChooseQuickProvisionOwnership(roleType)) return []

  const mode = form.scopeMode || QUICK_PROVISION_SCOPE_MODES.CURRENT
  if (mode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) {
    const errors = []
    if (!form.targetdomainid) errors.push('Select a Department boundary for the target Account.')
    if (!form.targetaccount) errors.push('Select the target Account.')
    return errors
  }
  if (mode === QUICK_PROVISION_SCOPE_MODES.PROJECT && !form.targetprojectid) {
    return ['Select the target Project.']
  }
  if (!Object.values(QUICK_PROVISION_SCOPE_MODES).includes(mode)) {
    return ['Select a valid deployment scope.']
  }
  return []
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

export function validateQuickProvisionCompute (form = {}, offerings = []) {
  const errors = []
  if (!form.serviceofferingid) return errors

  const offering = findOffering(offerings, form.serviceofferingid)
  if (!offering) {
    errors.push('The selected Compute Profile is no longer available.')
    return errors
  }

  if (offering.iscustomized) {
    if (!isPositiveInteger(form.cpunumber)) errors.push('The selected custom Compute Profile requires a positive whole-number CPU count.')
    if (!isPositiveInteger(form.cpuspeed)) errors.push('The selected custom Compute Profile requires a positive CPU speed in MHz.')
    if (!isPositiveInteger(form.memory)) errors.push('The selected custom Compute Profile requires positive memory in MiB.')
  }

  if (offering.diskofferingstrictness && form.rootdiskofferingid) {
    if (!offering.diskofferingid || offering.diskofferingid !== form.rootdiskofferingid) {
      errors.push('The selected Compute Profile enforces its linked root Storage Profile and cannot use this root override.')
    }
  }
  return errors
}

export function validateQuickProvisionRootStorage (form = {}, offerings = []) {
  const errors = []
  if (!form.rootdiskofferingid) {
    if (form.rootdisksize !== undefined && form.rootdisksize !== null && form.rootdisksize !== '' && !isPositiveNumber(form.rootdisksize)) {
      errors.push('Root disk size must be a positive number.')
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
  if (offering.iscustomized && !isPositiveNumber(form.rootdisksize)) {
    errors.push('The selected root Storage Profile requires a positive root disk size.')
  } else if (form.rootdisksize !== undefined && form.rootdisksize !== null && form.rootdisksize !== '' && !isPositiveNumber(form.rootdisksize)) {
    errors.push('Root disk size must be a positive number.')
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
    if (offering.iscustomized && !isPositiveNumber(volume.size)) {
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

export function validateQuickProvisionExistingVolumes (volumeIds = [], volumes = []) {
  const errors = []
  const inventory = new Map((Array.isArray(volumes) ? volumes : []).map(volume => [volume.id, volume]))
  ;(Array.isArray(volumeIds) ? volumeIds : []).forEach(volumeId => {
    const volume = inventory.get(volumeId)
    if (!volume) {
      errors.push('A selected existing data volume is no longer available in this deployment scope.')
      return
    }
    if (volume.virtualmachineid) {
      errors.push(`${volume.name || 'A selected data volume'} is already attached to a virtual machine.`)
      return
    }
    if (volume.state && String(volume.state).toLowerCase() !== 'ready') {
      errors.push(`${volume.name || 'A selected data volume'} is not in Ready state.`)
    }
  })
  return errors
}

export function buildQuickProvisionDeployParams ({
  form,
  networkType,
  storageProfiles = [],
  computeProfiles = [],
  scopeParams = {},
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

  const backwardsCompatibleScope = projectId ? { projectid: projectId } : {}
  Object.assign(params, Object.keys(scopeParams || {}).length > 0 ? scopeParams : backwardsCompatibleScope)

  const computeOffering = findOffering(computeProfiles, form.serviceofferingid)
  if (computeOffering?.iscustomized) {
    params['details[0].cpuNumber'] = Number(form.cpunumber)
    params['details[0].cpuSpeed'] = Number(form.cpuspeed)
    params['details[0].memory'] = Number(form.memory)
  }
  if (form.keypair) params.keypair = form.keypair

  // A strict Compute Profile owns its root Storage Profile. Never emit a stale
  // browser-side root override in that case, even if the user changed profiles
  // after making a prior selection.
  if (form.rootdiskofferingid && !computeOffering?.diskofferingstrictness) {
    params.overridediskofferingid = form.rootdiskofferingid
  }
  if (isPositiveNumber(form.rootdisksize)) params.rootdisksize = Number(form.rootdisksize)

  const volumes = Array.isArray(form.dataVolumes) ? form.dataVolumes : []
  volumes.forEach((volume, index) => {
    const offering = findOffering(storageProfiles, volume.diskofferingid)
    if (!offering) return
    const prefix = `datadisksdetails[${index}]`
    params[`${prefix}.diskofferingid`] = volume.diskofferingid
    params[`${prefix}.deviceid`] = index + 1
    if (offering.iscustomized && isPositiveNumber(volume.size)) params[`${prefix}.size`] = Number(volume.size)
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

export function buildQuickProvisionBackupAssignmentParams (virtualMachineId, backupOfferingId) {
  if (!virtualMachineId || !backupOfferingId) return null
  return {
    virtualmachineid: virtualMachineId,
    backupofferingid: backupOfferingId
  }
}

export function quickProvisionBlockingIssues ({
  form,
  roleType,
  networkType,
  storageProfiles = [],
  computeProfiles = [],
  existingVolumes = [],
  backupReady = true,
  kvmSiteReady = false,
  imageReady = false
}) {
  const issues = []
  if (!form.name) issues.push('Enter a VM name.')
  issues.push(...validateQuickProvisionOwnership({ form, roleType }))
  if (!form.zoneid) issues.push('Select a Site.')
  if (form.zoneid && !kvmSiteReady) issues.push('KVM availability for the Site is not verified.')
  if (!form.templateid) issues.push('Select an OS Image.')
  if (form.templateid && !imageReady) issues.push('The selected OS Image has not passed the KVM preflight.')
  if (!form.serviceofferingid) issues.push('Select a Compute Profile.')
  issues.push(...validateQuickProvisionCompute(form, computeProfiles))
  if (networkType !== 'Basic' && !form.networkid) issues.push('Select a Network Blueprint.')
  issues.push(...validateQuickProvisionRootStorage(form, storageProfiles))
  issues.push(...validateQuickProvisionDataVolumes(form.dataVolumes, storageProfiles))
  issues.push(...validateQuickProvisionExistingVolumes(form.existingvolumeids, existingVolumes))
  if (form.backupofferingid && !backupReady) issues.push('The selected Protection Plan cannot be assigned with the currently available provider APIs.')
  return issues
}
