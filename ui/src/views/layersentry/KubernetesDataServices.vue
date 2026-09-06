<!-- Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements. See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership. The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License. You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License. -->

<template>
  <div class="layersentry-k8s-services">
    <a-page-header
      title="Kubernetes & Data Services"
      sub-title="LayerSentry-managed RKE2, DBaaS, APaaS and Streaming on CloudStack KVM" />

    <a-alert
      v-if="!kubernetesReadiness.ready"
      type="warning"
      show-icon
      class="readiness-alert">
      <template #message>Release qualification is still blocked</template>
      <template #description>
        Customer mutations remain disabled until the exact release gates below have passed. This page intentionally fails closed instead of presenting an unsafe provisioning workflow.
      </template>
    </a-alert>

    <a-row :gutter="16" class="summary-row">
      <a-col :xs="24" :md="12" :xl="6" v-for="(service, key) in catalog" :key="key">
        <a-card class="service-card" :bordered="true">
          <template #title>{{ service.title }}</template>
          <template #extra>
            <a-tag :color="readiness(key).ready ? 'success' : 'warning'">
              {{ readiness(key).ready ? 'Ready' : 'Blocked' }}
            </a-tag>
          </template>
          <p>{{ service.description }}</p>
          <a-space wrap>
            <a-tag v-for="product in service.products" :key="product">{{ product }}</a-tag>
          </a-space>
        </a-card>
      </a-col>
    </a-row>

    <a-card title="Release candidate" class="section-card">
      <a-descriptions :column="3" bordered size="small">
        <a-descriptions-item label="CloudStack">{{ release.cloudstack }}</a-descriptions-item>
        <a-descriptions-item label="CAPI">{{ release.capi }}</a-descriptions-item>
        <a-descriptions-item label="CAPC">{{ release.capc }}</a-descriptions-item>
        <a-descriptions-item label="CAPRKE2">{{ release.caprke2 }}</a-descriptions-item>
        <a-descriptions-item label="RKE2">{{ release.rke2 }}</a-descriptions-item>
        <a-descriptions-item label="Status">
          <a-tag color="warning">{{ release.status }}</a-tag>
        </a-descriptions-item>
      </a-descriptions>
      <p class="hint">
        This is the Workstream E Lane B qualification candidate, not a production support claim.
      </p>
    </a-card>

    <a-card title="Mandatory release gates" class="section-card">
      <a-table
        :dataSource="gateRows"
        :columns="gateColumns"
        :pagination="false"
        rowKey="key"
        size="small">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.passed ? 'success' : 'error'">
              {{ record.passed ? 'PASSED' : 'BLOCKED' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'services'">
            <a-space wrap>
              <a-tag v-for="service in record.services" :key="service">{{ service.toUpperCase() }}</a-tag>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-tabs v-model:activeKey="activeTab" class="section-card">
      <a-tab-pane key="kubernetes" tab="Kubernetes">
        <a-row :gutter="24">
          <a-col :xs="24" :xl="12">
            <a-card title="Cluster request">
              <a-form layout="vertical">
                <a-form-item label="Cluster name">
                  <a-input v-model:value="clusterDraft.name" placeholder="team-a" />
                </a-form-item>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="Site">
                      <a-input v-model:value="clusterDraft.zoneid" placeholder="CloudStack Site UUID" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="Network Blueprint">
                      <a-input v-model:value="clusterDraft.networkid" placeholder="Network UUID" />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="Cluster Profile">
                      <a-select v-model:value="clusterDraft.clusterClass">
                        <a-select-option value="layersentry-standard-rke2">Standard RKE2</a-select-option>
                        <a-select-option value="layersentry-secure-rke2">Secure RKE2</a-select-option>
                        <a-select-option value="layersentry-dbaas-rke2">DBaaS RKE2</a-select-option>
                        <a-select-option value="layersentry-kafka-rke2">Kafka RKE2</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="Primary CNI">
                      <a-select v-model:value="clusterDraft.cni">
                        <a-select-option value="cilium">Cilium</a-select-option>
                        <a-select-option value="canal">Canal</a-select-option>
                        <a-select-option value="calico">Calico</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-form-item label="Control-plane replicas">
                  <a-input-number v-model:value="clusterDraft.controlPlaneReplicas" :min="3" :step="2" />
                </a-form-item>
                <a-divider>Worker pool</a-divider>
                <a-row :gutter="12">
                  <a-col :span="8"><a-input v-model:value="clusterDraft.nodePools[0].name" placeholder="workers" /></a-col>
                  <a-col :span="8"><a-input v-model:value="clusterDraft.nodePools[0].serviceofferingid" placeholder="Compute Profile UUID" /></a-col>
                  <a-col :span="8"><a-input v-model:value="clusterDraft.nodePools[0].templateid" placeholder="RKE2 Image UUID" /></a-col>
                </a-row>
                <a-form-item label="Worker replicas" class="top-gap">
                  <a-input-number v-model:value="clusterDraft.nodePools[0].replicas" :min="1" />
                </a-form-item>
                <a-alert v-if="clusterErrors.length" type="error" show-icon>
                  <template #message>Request is not executable</template>
                  <template #description>
                    <ul><li v-for="error in clusterErrors" :key="error">{{ error }}</li></ul>
                  </template>
                </a-alert>
                <a-button
                  type="primary"
                  class="top-gap"
                  :disabled="!canCreateCluster"
                  @click="previewPlan('kubernetes')">
                  Review controller plan
                </a-button>
              </a-form>
            </a-card>
          </a-col>
          <a-col :xs="24" :xl="12">
            <controller-plan :plan="controllerPlan" />
          </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="dbaas" tab="DBaaS">
        <a-alert
          v-if="!dbaasReadiness.ready"
          type="error"
          show-icon
          message="Stateful DBaaS is blocked by release evidence gates">
          <template #description>
            CAPC must preserve CSI/unowned DATADISK volumes during Machine deletion/replacement before PostgreSQL/MySQL/MongoDB/Redis/Valkey provisioning can be enabled.
          </template>
        </a-alert>
        <a-card title="DBaaS target contract" class="top-gap">
          <a-descriptions bordered :column="2" size="small">
            <a-descriptions-item label="Production topology">3 RKE2 control plane + 4 DB workers</a-descriptions-item>
            <a-descriptions-item label="Persistent storage">Certified NVMe CSI/PVC only</a-descriptions-item>
            <a-descriptions-item label="First engine">PostgreSQL</a-descriptions-item>
            <a-descriptions-item label="Provider">OpenEverest after release qualification</a-descriptions-item>
            <a-descriptions-item label="Later engines">MySQL, MongoDB, Redis, Valkey</a-descriptions-item>
            <a-descriptions-item label="Day-2">Backup, restore, PITR, monitoring, maintenance</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="apaas" tab="APaaS">
        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-card title="OpenBao">
              <p>HA secret-management service installed through the LayerSentry package catalog and central Flux.</p>
              <a-button :disabled="!apaasReadiness.ready">Create OpenBao service</a-button>
            </a-card>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-card title="Harbor">
              <p>HA registry service with a bootstrap path that does not depend on the registry instance being created.</p>
              <a-button :disabled="!apaasReadiness.ready">Create Harbor service</a-button>
            </a-card>
          </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="streaming" tab="Streaming">
        <a-card title="Kafka / Strimzi">
          <p>Kafka is reconciled by Strimzi and uses protocol-correct listeners/VIPs. A generic HTTP Gateway is not assumed to be a Kafka listener.</p>
          <a-button :disabled="!streamingReadiness.ready">Create Kafka service</a-button>
        </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script>
import { defineComponent, h } from 'vue'
import {
  K8S_HARD_GATES,
  K8S_RELEASE_CANDIDATE,
  SERVICE_CATALOG,
  buildControllerPlan,
  normaliseReleaseGates,
  serviceReadiness,
  validateClusterDraft
} from './k8sDataServices'

const ControllerPlan = defineComponent({
  name: 'ControllerPlan',
  props: {
    plan: { type: Array, default: () => [] }
  },
  render () {
    return h('div', { class: 'controller-plan' }, [
      h('h3', 'Controller ownership plan'),
      this.plan.length
        ? h('ol', this.plan.map(step => h('li', { key: `${step.owner}:${step.action}` }, [
          h('strong', `${step.owner}: `),
          step.action
        ])))
        : h('p', 'Complete the request and pass all release gates to review the owned-controller plan.')
    ])
  }
})

export default {
  name: 'KubernetesDataServices',
  components: { ControllerPlan },
  data () {
    const configuredGates = this.$config?.layersentry?.kubernetes?.releaseGates || {}
    return {
      activeTab: 'kubernetes',
      release: K8S_RELEASE_CANDIDATE,
      catalog: SERVICE_CATALOG,
      gates: normaliseReleaseGates(configuredGates),
      controllerPlan: [],
      clusterDraft: {
        name: '',
        zoneid: '',
        networkid: '',
        clusterClass: 'layersentry-standard-rke2',
        cni: 'cilium',
        controlPlaneReplicas: 3,
        nodePools: [{
          name: 'workers',
          replicas: 3,
          serviceofferingid: '',
          templateid: '',
          directNodeDisks: 0
        }]
      },
      gateColumns: [
        { title: 'Gate', dataIndex: 'label', key: 'label' },
        { title: 'Affected services', dataIndex: 'services', key: 'services' },
        { title: 'Status', key: 'status', width: 120 }
      ]
    }
  },
  computed: {
    gateRows () {
      return K8S_HARD_GATES.map(gate => ({ ...gate, passed: this.gates[gate.key] === true }))
    },
    kubernetesReadiness () { return serviceReadiness('kubernetes', this.gates) },
    dbaasReadiness () { return serviceReadiness('dbaas', this.gates) },
    apaasReadiness () { return serviceReadiness('apaas', this.gates) },
    streamingReadiness () { return serviceReadiness('streaming', this.gates) },
    clusterErrors () { return validateClusterDraft(this.clusterDraft) },
    canCreateCluster () {
      return this.kubernetesReadiness.ready && this.clusterErrors.length === 0
    }
  },
  methods: {
    readiness (service) {
      return serviceReadiness(service, this.gates)
    },
    previewPlan (service) {
      this.controllerPlan = buildControllerPlan(service, this.clusterDraft)
    }
  }
}
</script>

<style scoped lang="less">
.layersentry-k8s-services {
  .readiness-alert { margin-bottom: 16px; }
  .summary-row { margin-bottom: 16px; }
  .service-card { height: 100%; margin-bottom: 16px; }
  .section-card { margin-bottom: 16px; }
  .hint { margin: 12px 0 0; color: rgba(0, 0, 0, 0.55); }
  .top-gap { margin-top: 16px; }
  .controller-plan {
    border: 1px solid #f0f0f0;
    border-radius: 2px;
    padding: 20px;
    min-height: 260px;
  }
  ul { margin-bottom: 0; }
}
</style>
