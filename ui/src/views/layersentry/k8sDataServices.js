// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0

export const K8S_RELEASE_CANDIDATE = Object.freeze({
  cloudstack: '4.22.1.1',
  capi: '1.13.5',
  capc: '0.6.1',
  caprke2: '0.25.2',
  rke2: '1.36.4+rke2r1',
  kubernetes: '1.36.x',
  status: 'PENDING'
})

export const K8S_HARD_GATES = Object.freeze([
  {
    key: 'tupleReconciliation',
    label: 'CAPI/CAPC/CAPRKE2 reconciliation',
    services: ['kubernetes', 'dbaas', 'apaas', 'streaming']
  },
  {
    key: 'endpoint6443',
    label: 'Kubernetes API endpoint TCP 6443',
    services: ['kubernetes', 'dbaas', 'apaas', 'streaming']
  },
  {
    key: 'endpoint9345',
    label: 'RKE2 registration endpoint TCP 9345',
    services: ['kubernetes', 'dbaas', 'apaas', 'streaming']
  },
  {
    key: 'fluxRemoteReconcile',
    label: 'Central Flux remote reconciliation',
    services: ['kubernetes', 'dbaas', 'apaas', 'streaming']
  },
  {
    key: 'capcVolumeOwnershipSafe',
    label: 'CAPC Machine deletion preserves CSI/unowned DATADISK volumes',
    services: ['dbaas', 'apaas', 'streaming']
  },
  {
    key: 'csiProjectScope',
    label: 'CloudStack CSI project isolation',
    services: ['dbaas']
  },
  {
    key: 'statefulMachineReplacement',
    label: 'Stateful Machine replacement data survival',
    services: ['dbaas', 'apaas', 'streaming']
  },
  {
    key: 'backupRestore',
    label: 'Backup and restore validation',
    services: ['dbaas']
  }
])

export const SERVICE_CATALOG = Object.freeze({
  kubernetes: {
    title: 'LayerSentry K8s',
    description: 'RKE2 clusters managed through CAPI, CAPC and CAPRKE2 on CloudStack KVM.',
    products: ['Standard RKE2', 'Secure RKE2', 'DBaaS RKE2', 'Kafka RKE2', 'GPU RKE2']
  },
  dbaas: {
    title: 'LayerSentry DBaaS',
    description: 'Managed data services on dedicated LayerSentry RKE2 clusters.',
    products: ['PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Valkey']
  },
  apaas: {
    title: 'LayerSentry APaaS',
    description: 'Curated application platform packages reconciled by central Flux.',
    products: ['OpenBao', 'Harbor']
  },
  streaming: {
    title: 'LayerSentry Streaming',
    description: 'Certified streaming packages with protocol-correct network exposure.',
    products: ['Kafka / Strimzi']
  }
})

export function normaliseReleaseGates (input = {}) {
  return K8S_HARD_GATES.reduce((result, gate) => {
    result[gate.key] = input[gate.key] === true
    return result
  }, {})
}

export function serviceBlockingGates (service, gates = {}) {
  const safeGates = normaliseReleaseGates(gates)
  return K8S_HARD_GATES
    .filter(gate => gate.services.includes(service))
    .filter(gate => !safeGates[gate.key])
}

export function serviceReadiness (service, gates = {}) {
  const blockers = serviceBlockingGates(service, gates)
  return {
    service,
    ready: blockers.length === 0,
    blockers,
    status: blockers.length === 0 ? 'SOURCE_COMPLETE' : 'BLOCKED'
  }
}

export function validateClusterDraft (draft = {}) {
  const errors = []
  if (!draft.name) errors.push('Enter a cluster name.')
  if (!draft.zoneid) errors.push('Select a Site.')
  if (!draft.networkid) errors.push('Select a Network Blueprint.')
  if (!draft.clusterClass) errors.push('Select a Cluster Profile.')
  if (!draft.cni) errors.push('Select a primary CNI.')
  if (!Number.isInteger(Number(draft.controlPlaneReplicas)) || Number(draft.controlPlaneReplicas) < 3 || Number(draft.controlPlaneReplicas) % 2 === 0) {
    errors.push('Control plane requires an odd replica count of at least 3.')
  }
  const pools = Array.isArray(draft.nodePools) ? draft.nodePools : []
  if (!pools.length) errors.push('Add at least one worker pool.')
  pools.forEach((pool, index) => {
    const label = pool.name || `Worker pool ${index + 1}`
    if (!pool.serviceofferingid) errors.push(`${label} requires a Compute Profile.`)
    if (!pool.templateid) errors.push(`${label} requires an RKE2 Image.`)
    if (!Number.isInteger(Number(pool.replicas)) || Number(pool.replicas) < 1) errors.push(`${label} requires at least one node.`)
    if (Number(pool.directNodeDisks || 0) > 0) errors.push(`${label}: direct node disks require certified NodeDiskSet ownership.`)
  })
  return errors
}

export function validateDatabaseDraft (draft = {}, storageProfiles = []) {
  const errors = []
  if (!draft.name) errors.push('Enter a database service name.')
  if (!draft.clusterid) errors.push('Select a Data Services cluster.')
  if (!draft.engine) errors.push('Select a database engine.')
  if (!draft.version) errors.push('Select an engine version.')
  if (!draft.storageProfileId) errors.push('Select an NVMe Database Storage Profile.')
  const storage = storageProfiles.find(profile => profile.id === draft.storageProfileId)
  if (draft.storageProfileId && !storage) errors.push('The selected Storage Profile is no longer available.')
  if (storage && (storage.certified !== true || storage.database !== true || storage.nvme !== true || storage.directNodeDisk === true)) {
    errors.push('DBaaS requires a certified NVMe CSI/PVC Database Storage Profile.')
  }
  if (!Number.isFinite(Number(draft.storageSizeGiB)) || Number(draft.storageSizeGiB) <= 0) errors.push('Database storage size must be positive.')
  if (!Number.isInteger(Number(draft.replicas)) || Number(draft.replicas) < 1) errors.push('Database replicas must be a positive integer.')
  return errors
}

export function validatePackageDraft (draft = {}) {
  const errors = []
  const supported = ['openbao', 'harbor', 'strimzi-kafka']
  if (!draft.name) errors.push('Enter a service name.')
  if (!draft.clusterid) errors.push('Select a Kubernetes cluster.')
  if (!supported.includes(draft.package)) errors.push('Select a supported LayerSentry package.')
  if (!draft.version) errors.push('Select a certified package version.')
  if (!['private', 'l4', 'gateway'].includes(draft.exposeMode || 'private')) errors.push('Select a valid exposure mode.')
  if ((draft.exposeMode === 'l4' || draft.exposeMode === 'gateway') && !(Array.isArray(draft.frontendIds) && draft.frontendIds.length)) {
    errors.push('External exposure requires at least one LayerSentry Frontend/VIP.')
  }
  return errors
}

export function buildControllerPlan (service, draft = {}) {
  if (service === 'kubernetes') {
    return [
      { owner: 'LayerSentry', action: 'Resolve certified release/profile' },
      { owner: 'CloudStack', action: 'Resolve Site/network/compute/image inputs' },
      { owner: 'CAPI/CAPC', action: 'Reconcile CloudStack infrastructure Machines' },
      { owner: 'CAPRKE2', action: 'Bootstrap and join RKE2 servers/nodes automatically' },
      { owner: 'Endpoint authority', action: 'Reconcile one HA frontend for TCP 6443 and 9345' },
      { owner: 'CAPI', action: 'Reconcile worker MachineDeployments' },
      { owner: 'CloudStack CCM', action: 'Reconcile cloud-provider integration' },
      { owner: 'Flux', action: 'Reconcile selected baseline packages' },
      { owner: 'LayerSentry', action: 'Verify readiness and publish evidence' }
    ]
  }
  if (service === 'dbaas') {
    return [
      { owner: 'LayerSentry', action: 'Resolve policy, engine and certified storage profile' },
      { owner: 'Flux', action: 'Ensure the selected DB provider/operator' },
      { owner: ['postgresql', 'mysql', 'mongodb'].includes(draft.engine) ? 'OpenEverest' : 'Redis/Valkey provider', action: 'Reconcile database lifecycle' },
      { owner: 'Database operator', action: 'Reconcile backup/PITR/maintenance policy' },
      { owner: 'LayerSentry', action: 'Verify health, recovery and audit evidence' }
    ]
  }
  return [
    { owner: 'LayerSentry', action: 'Resolve package policy/version' },
    { owner: 'Flux', action: 'Reconcile package on the selected remote cluster' },
    { owner: 'L4/Gateway/OEM owner', action: 'Reconcile declared Frontend/VIP lifecycle' },
    { owner: 'LayerSentry', action: 'Verify package readiness and publish evidence' }
  ]
}
