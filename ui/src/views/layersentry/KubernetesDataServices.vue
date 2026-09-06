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
    <a-page-header title="Kubernetes & Data Services" sub-title="Provision and operate managed Kubernetes clusters in your project." />
    <a-alert v-if="error" type="error" show-icon :message="error" class="section-card" />
    <a-alert v-if="notice" type="info" show-icon :message="notice" class="section-card" />
    <a-space class="section-card" wrap>
      <label for="k8s-project">Project</label>
      <a-select
id="k8s-project"
v-model:value="projectId"
placeholder="Select a project"
:options="projectOptions"
:loading="loadingProjects"
class="project-select"
:disabled="submitting" />
      <a-button :loading="loading" :disabled="submitting" @click="refresh">Refresh</a-button>
    </a-space>
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="kubernetes" tab="Kubernetes">
        <a-alert v-if="!serverReady" type="warning" show-icon message="Cluster provisioning is unavailable" class="section-card">
          <template #description>{{ readinessDescription }}</template>
        </a-alert>
        <a-row :gutter="24">
          <a-col :xs="24" :xl="12">
            <a-card title="Create cluster" class="section-card">
              <a-form layout="vertical" @submit.prevent="createCluster">
                <a-form-item label="Cluster name"><a-input v-model:value="draft.name" placeholder="team-a" :maxlength="63" :disabled="requestLocked" /></a-form-item>
                <a-form-item label="Site"><a-select v-model:value="draft.zone_id" :options="zoneOptions" placeholder="Select an enabled Site" :disabled="requestLocked || !projectId" /></a-form-item>
                <a-form-item label="Network"><a-select v-model:value="draft.network_id" :options="networkOptions" placeholder="Select an implemented network" :loading="loadingDiscovery" :disabled="requestLocked || !draft.zone_id" /></a-form-item>
                <a-form-item label="Kubernetes endpoint"><a-select v-model:value="draft.api_frontend_id" :options="frontendOptions" placeholder="Select a reserved project IP" :loading="loadingDiscovery" :disabled="requestLocked || !draft.zone_id" /></a-form-item>
                <a-form-item label="Cluster profile"><a-select v-model:value="draft.cluster_class" :disabled="requestLocked">
                  <a-select-option value="layersentry-standard-rke2">Standard RKE2</a-select-option>
                  <a-select-option value="layersentry-secure-rke2">Secure RKE2</a-select-option>
                </a-select></a-form-item>
                <a-form-item label="Primary network provider"><a-select v-model:value="draft.cni" :disabled="requestLocked">
                  <a-select-option value="cilium">Cilium</a-select-option><a-select-option value="canal">Canal</a-select-option><a-select-option value="calico">Calico</a-select-option>
                </a-select></a-form-item>
                <a-alert v-if="discoveryWarning" type="info" show-icon :message="discoveryWarning" class="section-card" />
                <a-divider>Control plane</a-divider>
                <a-form-item label="Compute profile"><a-select v-model:value="draft.control_plane_service_offering_id" :options="offeringOptions" placeholder="Select a compute profile" :disabled="requestLocked" /></a-form-item>
                <a-form-item label="Node image"><a-select v-model:value="draft.control_plane_image_id" :options="imageOptions" placeholder="Select an available KVM node image" :disabled="requestLocked" /></a-form-item>
                <a-form-item label="Control-plane nodes"><a-input-number v-model:value="draft.control_plane_replicas" :min="3" :max="9" :step="2" :disabled="requestLocked" /></a-form-item>
                <a-divider>Worker pool</a-divider>
                <a-form-item label="Compute profile"><a-select v-model:value="draft.node_pools[0].service_offering_id" :options="offeringOptions" placeholder="Select a compute profile" :disabled="requestLocked" /></a-form-item>
                <a-form-item label="Node image"><a-select v-model:value="draft.node_pools[0].image_id" :options="imageOptions" placeholder="Select an available KVM node image" :disabled="requestLocked" /></a-form-item>
                <a-form-item label="Worker nodes"><a-input-number v-model:value="draft.node_pools[0].replicas" :min="1" :max="100" :disabled="requestLocked" /></a-form-item>
                <p>Infrastructure availability and release qualification are checked by the service before deployment.</p>
                <a-button type="primary" :disabled="!canCreate" :loading="submitting" @click="createCluster">Create cluster</a-button>
              </a-form>
            </a-card>
          </a-col>
          <a-col :xs="24" :xl="12">
            <a-card title="Clusters" class="section-card">
              <a-empty v-if="!clusters.length && !loading && !error && readiness" description="No managed clusters reported for this project" />
              <a-list v-else :data-source="clusters" :loading="loading">
                <template #renderItem="{ item }"><a-list-item>
                  <a-button type="link" @click="selectCluster(item)">{{ item.name }}</a-button>
                  <a-tag :color="item.ready === true ? 'success' : 'default'">{{ item.ready === true ? 'Ready' : (item.phase || 'UNKNOWN') }}</a-tag>
                </a-list-item></template>
              </a-list>
            </a-card>
            <a-card v-if="selectedCluster" :title="selectedCluster.name" class="section-card">
              <p role="status">{{ selectedCluster.ready === true ? 'Cluster reports ready' : 'Cluster is not ready' }} · Control plane: {{ selectedCluster.controlPlaneReady === true ? 'Ready' : 'Not ready' }}</p>
              <a-form layout="vertical">
                <a-form-item label="Worker pool"><a-select v-model:value="scalePool" :options="poolOptions" :disabled="requestLocked" placeholder="Select a worker pool" /></a-form-item>
                <a-form-item label="Desired workers"><a-input-number v-model:value="scaleReplicas" :min="1" :max="100" :disabled="requestLocked" /></a-form-item>
                <a-button :disabled="!canScale" @click="scaleCluster">Scale workers</a-button>
                <a-divider />
                <p>Delete removes the managed cluster. Workload volumes are retained by the service policy.</p>
                <a-form-item label="Type the cluster name to confirm deletion"><a-input v-model:value="deleteConfirmation" :disabled="requestLocked" /></a-form-item>
                <a-button danger :disabled="!canDelete" @click="deleteCluster">Delete cluster</a-button>
              </a-form>
            </a-card>
          </a-col>
        </a-row>
        <a-card title="Operation history" class="section-card">
          <p v-if="pollingPaused" role="status">Automatic refresh has paused. Refresh to read the current state; no operation was resubmitted.</p>
          <a-alert v-if="uncertainAttempt" type="warning" show-icon message="Submission outcome is unknown" class="section-card">
            <template #description>Review operation history. Retry sends the exact original request identifier so the service can recover the existing operation.</template>
          </a-alert>
          <a-button v-if="uncertainAttempt" :disabled="submitting" @click="submitAttempt(uncertainAttempt)">Retry exact request</a-button>
          <a-table :columns="operationColumns" :data-source="operations" row-key="id" :pagination="false" :scroll="{ x: 650 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'"><span role="status">{{ record.status }} ({{ record.stepIndex }}/{{ record.stepCount }})</span></template>
              <template v-else-if="column.key === 'detail'">{{ record.lastError || record.recovery || '—' }}</template>
            </template>
          </a-table>
          <a-button v-if="nextCursor" :disabled="loading" @click="loadMoreOperations">Load earlier operations</a-button>
        </a-card>
      </a-tab-pane>
      <a-tab-pane v-for="service in otherServices" :key="service.key" :tab="service.title">
        <a-alert type="warning" show-icon :message="service.title + ' provisioning is unavailable'" :description="service.description" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script>
import { getAPI } from '@/api'
import { kubernetesRequest, mutationAttempt, scopeQuery, operationNeedsPolling, discoverKubernetesResources } from '@/api/layersentryKubernetes'

const emptyDraft = () => ({
  name: '',
  zone_id: undefined,
  network_id: undefined,
  api_frontend_id: undefined,
  cluster_class: 'layersentry-standard-rke2',
  channel: 'certified',
  cni: 'cilium',
  control_plane_replicas: 3,
  control_plane_service_offering_id: undefined,
  control_plane_image_id: undefined,
  node_pools: [{ name: 'workers', replicas: 3, service_offering_id: undefined, image_id: undefined, direct_node_disks: 0 }]
})
const dnsName = value => typeof value === 'string' && /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(value)
const options = rows => rows.map(row => ({ value: row.id, label: row.displaytext || row.name || row.ipaddress || row.id }))

export default {
  name: 'KubernetesDataServices',
  data () {
    return {
      activeTab: 'kubernetes',
      projectId: undefined,
      projects: [],
      zones: [],
      networks: [],
      offerings: [],
      images: [],
      frontends: [],
      readiness: null,
      draft: emptyDraft(),
      loading: false,
      loadingProjects: false,
      loadingDiscovery: false,
      submitting: false,
      error: '',
      notice: '',
      operations: [],
      nextCursor: null,
      clusters: [],
      selectedCluster: null,
      scalePool: undefined,
      scaleReplicas: 3,
      deleteConfirmation: '',
      uncertainAttempt: null,
      generation: 0,
      discoveryGeneration: 0,
      selectionGeneration: 0,
      runtimeGeneration: 0,
      pollTimer: null,
      pollCount: 0,
      pollingPaused: false,
      aborter: null,
      operationColumns: [
        { title: 'Cluster', dataIndex: 'targetName', key: 'targetName' },
        { title: 'Action', dataIndex: 'kind', key: 'kind' },
        { title: 'Operation ID', dataIndex: 'id', key: 'id' },
        { title: 'Status', key: 'status' },
        { title: 'Details', key: 'detail' }
      ],
      otherServices: [
        { key: 'dbaas', title: 'DBaaS', description: 'Database provisioning requires a qualified database operator, certified persistent storage and verified backup and recovery. This deployment has not exposed a qualified database lifecycle service.' },
        { key: 'apaas', title: 'APaaS', description: 'OpenBao and Harbor require a qualified package lifecycle service and verified persistence, recovery and upgrades. Application provisioning is not enabled in this deployment.' },
        { key: 'streaming', title: 'Streaming', description: 'Kafka requires a qualified Strimzi lifecycle service, storage and protocol-specific endpoints. Streaming provisioning is not enabled in this deployment.' }
      ]
    }
  },
  computed: {
    storeScope () { return JSON.stringify([this.$store?.getters?.userInfo?.id, this.$store?.getters?.project?.id, this.$store?.getters?.userInfo?.roletype]) },
    projectOptions () { return options(this.projects) },
    zoneOptions () { return options(this.zones) },
    networkOptions () { return options(this.networks) },
    offeringOptions () { return options(this.offerings) },
    imageOptions () { return options(this.images) },
    frontendOptions () { return options(this.frontends) },
    poolOptions () { return (this.selectedCluster?.nodePools || []).map(pool => ({ value: pool.name, label: `${pool.name} (${pool.replicas} desired)` })) },
    serverReady () { return this.readiness?.kubernetes === true && this.readiness?.gates?.capc_volume_ownership_safe === true },
    readinessDescription () {
      return !this.readiness ? 'The Kubernetes service must be reachable and report release readiness before provisioning is enabled.'
        : 'The installed release has not passed its required compatibility, endpoint or volume-safety gates. Contact your platform administrator.'
    },
    discoveryWarning () {
      if (!this.draft.zone_id || this.loadingDiscovery) return ''
      const missing = [[this.networks, 'implemented networks'], [this.frontends, 'reserved project IPs'], [this.offerings, 'fixed compute profiles'], [this.images, 'ready KVM images']].filter(([rows]) => !rows.length).map(([, label]) => label)
      return missing.length ? `This Site has no selectable ${missing.join(', ')}. Select another Site or ask your platform administrator to complete its prerequisites.` : ''
    },
    requestLocked () { return this.submitting || !!this.uncertainAttempt },
    canCreate () {
      const d = this.draft
      const pool = d.node_pools[0]
      return this.serverReady && !!this.projectId && !this.requestLocked && !this.loading && !this.loadingDiscovery &&
        dnsName(d.name) && this.zones.some(x => x.id === d.zone_id) && this.networks.some(x => x.id === d.network_id) &&
        this.frontends.some(x => x.id === d.api_frontend_id) &&
        [d.control_plane_service_offering_id, pool.service_offering_id].every(id => this.offerings.some(x => x.id === id)) &&
        [d.control_plane_image_id, pool.image_id].every(id => this.images.some(x => x.id === id)) &&
        Number.isInteger(d.control_plane_replicas) && d.control_plane_replicas >= 3 && d.control_plane_replicas % 2 === 1 &&
        Number.isInteger(pool.replicas) && pool.replicas >= 1 && !this.clusters.some(cluster => cluster.name === d.name) && !this.operations.some(op => op.targetName === d.name && operationNeedsPolling(op))
    },
    canScale () { return this.serverReady && !!this.projectId && !this.requestLocked && !!this.selectedCluster && this.poolOptions.some(p => p.value === this.scalePool) && Number.isInteger(this.scaleReplicas) && this.scaleReplicas >= 1 && !this.clusterBusy },
    canDelete () { return this.serverReady && !!this.projectId && !this.requestLocked && !!this.selectedCluster && this.deleteConfirmation === this.selectedCluster.name && !this.clusterBusy },
    clusterBusy () { return this.operations.some(op => op.targetName === this.selectedCluster?.name && operationNeedsPolling(op)) }
  },
  watch: {
    storeScope () { this.initialize() },
    projectId () { this.resetScope(); this.refresh() },
    'draft.zone_id' () { this.loadSiteDiscovery() }
  },
  mounted () { this.initialize() },
  beforeUnmount () { this.resetScope() },
  methods: {
    resetScope () {
      this.generation++; this.discoveryGeneration++; this.selectionGeneration++; this.runtimeGeneration++
      if (this.aborter) this.aborter.abort()
      this.aborter = new AbortController()
      clearTimeout(this.pollTimer); this.pollTimer = null
      this.readiness = null; this.operations = []; this.clusters = []; this.selectedCluster = null
      this.nextCursor = null; this.uncertainAttempt = null; this.submitting = false; this.error = ''; this.notice = ''
      this.draft = emptyDraft(); this.zones = []; this.networks = []; this.offerings = []; this.images = []; this.frontends = []
      this.pollCount = 0; this.pollingPaused = false; this.loadingDiscovery = false; this.loading = false
    },
    async initialize () {
      this.resetScope()
      const generation = this.generation
      this.projects = []; this.loadingProjects = true
      try {
        const projects = await discoverKubernetesResources(getAPI, 'listProjects', 'project', { ignoreproject: true, state: 'Active' }, () => generation === this.generation)
        if (generation !== this.generation) return
        this.projects = projects.filter(p => p.state === 'Active')
        const selected = this.$store?.getters?.project?.id
        const next = this.projects.some(p => p.id === selected) ? selected : this.projects[0]?.id
        if (this.projectId === next) await this.refresh()
        else this.projectId = next
      } catch (error) { if (generation === this.generation) this.error = 'Project discovery failed. Verify access and refresh.' } finally { if (generation === this.generation) this.loadingProjects = false }
    },
    async refresh () {
      if (this.submitting || this.loading) return
      if (!this.projects.length) { if (!this.loadingProjects) await this.initialize(); return }
      if (!this.projectId) return
      clearTimeout(this.pollTimer)
      const generation = this.generation
      this.loading = true; this.error = ''; this.pollCount = 0; this.pollingPaused = false
      try {
        const [readiness, zones] = await Promise.all([
          kubernetesRequest('/readiness', { signal: this.aborter.signal }),
          discoverKubernetesResources(getAPI, 'listZones', 'zone', { available: true, ignoreproject: true }, () => generation === this.generation)
        ])
        if (generation !== this.generation) return
        this.readiness = readiness
        this.zones = zones.filter(z => z.allocationstate === 'Enabled')
        await this.loadRuntime(generation)
      } catch (error) { if (generation === this.generation) { this.error = error.message; this.readiness = null } } finally {
        if (generation === this.generation) { this.loading = false; this.schedulePoll() }
      }
    },
    async loadSiteDiscovery () {
      const generation = this.generation
      const discovery = ++this.discoveryGeneration
      const zoneid = this.draft.zone_id
      this.networks = []; this.frontends = []; this.offerings = []; this.images = []
      this.draft.network_id = undefined; this.draft.api_frontend_id = undefined
      this.draft.control_plane_service_offering_id = undefined; this.draft.control_plane_image_id = undefined
      this.draft.node_pools[0].service_offering_id = undefined; this.draft.node_pools[0].image_id = undefined
      if (!zoneid || !this.projectId) return
      const current = () => generation === this.generation && discovery === this.discoveryGeneration
      this.loadingDiscovery = true
      try {
        const args = { zoneid, projectid: this.projectId }
        const read = (command, collection, extra) => discoverKubernetesResources(getAPI, command, collection, { ...args, ...extra }, current)
        const [networks, frontends, offerings, images] = await Promise.all([
          read('listNetworks', 'network', {}), read('listPublicIpAddresses', 'publicipaddress', {}),
          read('listServiceOfferings', 'serviceoffering', { issystem: false }),
          read('listTemplates', 'template', { templatefilter: 'executable', hypervisor: 'KVM' })
        ])
        if (!current()) return
        this.networks = networks.filter(n => n.zoneid === zoneid && n.state === 'Implemented')
        this.frontends = frontends.filter(ip => ip.zoneid === zoneid && ip.projectid === this.projectId && ip.state === 'Allocated')
        this.offerings = offerings.filter(o => o.issystem !== true && o.iscustomized !== true && o.state !== 'Inactive')
        this.images = images.filter(image => image.isready === true && image.hypervisor === 'KVM')
      } catch (error) { if (current()) this.error = 'Site resources could not be discovered. Refresh the Site before provisioning.' } finally { if (current()) this.loadingDiscovery = false }
    },
    async loadRuntime (generation) {
      const runtime = ++this.runtimeGeneration
      const query = scopeQuery(this.projectId)
      const [history, inventory] = await Promise.all([
        kubernetesRequest('/operations' + scopeQuery(this.projectId, { limit: 50 }), { signal: this.aborter.signal }),
        kubernetesRequest('/clusters' + query, { signal: this.aborter.signal })
      ])
      if (generation !== this.generation || runtime !== this.runtimeGeneration) return
      if (!Array.isArray(history.operations) || !Array.isArray(inventory.clusters)) throw new Error('Kubernetes service returned an invalid inventory.')
      this.operations = history.operations; this.nextCursor = history.nextCursor || null
      this.clusters = inventory.clusters
      if (this.selectedCluster) {
        const current = this.clusters.find(c => c.name === this.selectedCluster.name && c.namespace === this.selectedCluster.namespace)
        this.selectedCluster = current || null
      }
    },
    schedulePoll () {
      clearTimeout(this.pollTimer)
      if (!this.operations.some(operationNeedsPolling)) return
      if (++this.pollCount > 120) { this.pollingPaused = true; return }
      const generation = this.generation
      this.pollTimer = setTimeout(async () => {
        try { await this.loadRuntime(generation); if (generation === this.generation) this.schedulePoll() } catch (error) {
          if (generation === this.generation) { this.error = error.message; this.pollingPaused = true; this.readiness = null }
        }
      }, 5000)
    },
    async loadMoreOperations () {
      if (!this.nextCursor || this.loading) return
      const generation = this.generation
      this.loading = true
      try {
        const result = await kubernetesRequest('/operations' + scopeQuery(this.projectId, { limit: 50, after: this.nextCursor }), { signal: this.aborter.signal })
        if (generation !== this.generation) return
        if (!Array.isArray(result.operations)) throw new Error('Invalid operation history response.')
        const known = new Set(this.operations.map(op => op.id))
        this.operations.push(...result.operations.filter(op => !known.has(op.id))); this.nextCursor = result.nextCursor || null
      } catch (error) { if (generation === this.generation) this.error = error.message } finally { if (generation === this.generation) this.loading = false }
    },
    async selectCluster (cluster) {
      const generation = this.generation
      const selection = ++this.selectionGeneration
      this.selectedCluster = null; this.scalePool = undefined; this.deleteConfirmation = ''
      try {
        const result = await kubernetesRequest('/clusters/' + encodeURIComponent(cluster.name) + scopeQuery(this.projectId, { namespace: cluster.namespace }), { signal: this.aborter.signal })
        if (generation === this.generation && selection === this.selectionGeneration) this.selectedCluster = result.cluster
      } catch (error) { if (generation === this.generation && selection === this.selectionGeneration) this.error = error.message }
    },
    createCluster () {
      if (!this.canCreate) return
      this.submitAttempt(mutationAttempt('POST', '/clusters', { ...this.draft, project_id: this.projectId }))
    },
    scaleCluster () {
      if (!this.canScale) return
      this.submitAttempt(mutationAttempt('POST', '/clusters/' + this.selectedCluster.name + '/scale', {
        cluster_name: this.selectedCluster.name,
        namespace: this.selectedCluster.namespace,
        project_id: this.projectId,
        node_pool: this.scalePool,
        replicas: this.scaleReplicas
      }))
    },
    deleteCluster () {
      if (!this.canDelete) return
      this.submitAttempt(mutationAttempt('DELETE', '/clusters/' + this.selectedCluster.name, {
        cluster_name: this.selectedCluster.name,
        namespace: this.selectedCluster.namespace,
        project_id: this.projectId,
        confirm_cluster_name: this.deleteConfirmation,
        retain_workload_volumes: true
      }))
    },
    async submitAttempt (attempt) {
      if (this.submitting || !this.projectId || attempt.body.project_id !== this.projectId) return
      const generation = this.generation
      this.submitting = true; this.error = ''; this.notice = ''
      try {
        const result = await kubernetesRequest(attempt.path, { ...attempt, signal: this.aborter.signal })
        if (generation !== this.generation) return
        if (!result.operation?.id || result.operation.projectId !== this.projectId) throw new Error('Controller did not return the submitted operation.')
        this.uncertainAttempt = null
        this.operations = [result.operation, ...this.operations.filter(op => op.id !== result.operation.id)]
        this.notice = 'Request accepted. Operation history reports progress; acceptance does not mean the cluster is ready.'
        this.pollCount = 0; this.schedulePoll()
      } catch (error) {
        if (generation === this.generation) {
          this.error = error.message
          if (error.ambiguous || !error.status) this.uncertainAttempt = attempt
        }
      } finally { if (generation === this.generation) this.submitting = false }
    }
  }
}
</script>

<style scoped lang="less">
.layersentry-k8s-services {
  .section-card { margin-bottom: 16px; }
  .project-select { min-width: 240px; }
}
</style>
