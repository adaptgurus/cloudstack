// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0

import {
  buildControllerPlan,
  normaliseReleaseGates,
  serviceBlockingGates,
  serviceReadiness,
  validateClusterDraft,
  validateDatabaseDraft,
  validatePackageDraft
} from '@/views/layersentry/k8sDataServices'

describe('LayerSentry Kubernetes/Data Services product contract', () => {
  it('fails closed for unspecified release gates', () => {
    const gates = normaliseReleaseGates({ endpoint6443: true })
    expect(gates.endpoint6443).toBe(true)
    expect(gates.endpoint9345).toBe(false)
    expect(serviceReadiness('kubernetes', gates).ready).toBe(false)
  })

  it('requires the RKE2 9345 endpoint for Kubernetes', () => {
    const blockers = serviceBlockingGates('kubernetes', {
      tupleReconciliation: true,
      endpoint6443: true,
      endpoint9345: false,
      fluxRemoteReconcile: true
    })
    expect(blockers.map(item => item.key)).toContain('endpoint9345')
  })

  it('requires CAPC data safety before DBaaS', () => {
    const blockers = serviceBlockingGates('dbaas', {
      tupleReconciliation: true,
      endpoint6443: true,
      endpoint9345: true,
      fluxRemoteReconcile: true,
      capcVolumeOwnershipSafe: false,
      csiProjectScope: true,
      statefulMachineReplacement: true,
      backupRestore: true
    })
    expect(blockers.map(item => item.key)).toContain('capcVolumeOwnershipSafe')
  })

  it('rejects direct worker node disks until NodeDiskSet is certified', () => {
    const errors = validateClusterDraft({
      name: 'cluster-a',
      zoneid: 'zone-1',
      networkid: 'network-1',
      clusterClass: 'layersentry-standard-rke2',
      cni: 'cilium',
      controlPlaneReplicas: 3,
      nodePools: [{
        name: 'workers',
        replicas: 3,
        serviceofferingid: 'compute-1',
        templateid: 'image-1',
        directNodeDisks: 1
      }]
    })
    expect(errors.join(' ')).toContain('NodeDiskSet')
  })

  it('rejects non-NVMe or direct-disk database storage', () => {
    const errors = validateDatabaseDraft({
      name: 'orders-db',
      clusterid: 'cluster-1',
      engine: 'postgresql',
      version: '17',
      storageProfileId: 'slow',
      storageSizeGiB: 100,
      replicas: 3
    }, [{
      id: 'slow',
      certified: true,
      database: true,
      nvme: false,
      directNodeDisk: false
    }])
    expect(errors.join(' ')).toContain('NVMe')
  })

  it('requires a Frontend for external APaaS exposure', () => {
    const errors = validatePackageDraft({
      name: 'registry',
      clusterid: 'cluster-1',
      package: 'harbor',
      version: '2.14.0',
      exposeMode: 'gateway',
      frontendIds: []
    })
    expect(errors.join(' ')).toContain('Frontend')
  })

  it('keeps VM and application lifecycle ownership outside LayerSentry', () => {
    const k8sOwners = buildControllerPlan('kubernetes').map(item => item.owner)
    expect(k8sOwners).toContain('CAPI/CAPC')
    expect(k8sOwners).toContain('CAPRKE2')
    expect(k8sOwners).toContain('Flux')
    expect(k8sOwners).not.toContain('LayerSentry VM Scheduler')

    const dbOwners = buildControllerPlan('dbaas', { engine: 'postgresql' }).map(item => item.owner)
    expect(dbOwners).toContain('OpenEverest')
  })
})
