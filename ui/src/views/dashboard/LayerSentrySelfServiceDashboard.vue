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

<template>
  <div class="ls-self-service-dashboard">
    <section class="ls-self-service-hero">
      <div>
        <div class="ls-eyebrow">{{ $t('label.layersentry.self.service') }}</div>
        <div class="ls-title-row">
          <h1>{{ $t('label.dashboard') }}</h1>
          <a-tag color="blue">{{ $t(dashboardRoleLabel) }}</a-tag>
        </div>
        <p>{{ dashboardDescription }}</p>
        <div class="ls-scope">{{ scopeLabel }}</div>
      </div>
      <div class="ls-hero-actions">
        <router-link
          v-for="action in dashboardQuickActions"
          :key="action.key"
          :to="{ path: action.path }">
          <a-button type="primary">
            <rocket-outlined v-if="action.key === 'instance'" />
            {{ $t(action.label) }}
          </a-button>
        </router-link>
        <a-button :loading="loading" @click="refresh">
          <reload-outlined /> {{ $t('label.refresh') }}
        </a-button>
      </div>
    </section>

    <a-alert
      v-if="partialFailures.length"
      type="warning"
      show-icon
      class="ls-dashboard-alert"
      :message="$t('label.layersentry.partial.data', { sections: partialFailures.join(', ') })" />

    <a-row :gutter="[16, 16]">
      <a-col
        v-for="card in resourceCards"
        :key="card.key"
        :xs="24"
        :sm="12"
        :xl="8">
        <router-link :to="card.to" class="ls-resource-link">
          <a-card :bordered="false" class="ls-resource-card">
            <div class="ls-resource-card__icon"><component :is="card.icon" /></div>
            <div class="ls-resource-card__value">{{ displayCount(card.value) }}</div>
            <div class="ls-resource-card__label">{{ card.label }}</div>
            <div v-if="card.detail" class="ls-resource-card__detail">{{ card.detail }}</div>
          </a-card>
        </router-link>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="ls-secondary-row">
      <a-col :xs="24" :xl="12" v-if="hasApi('listVirtualMachines')">
        <a-card :bordered="false" class="ls-panel-card">
          <template #title>
            <div class="ls-card-title"><cloud-server-outlined /> Virtual Machine state</div>
          </template>
          <div class="ls-vm-state-grid">
            <router-link :to="{ path: '/vm', query: routeQuery({ hypervisor: 'KVM', state: 'running' }) }" class="ls-vm-state">
              <span class="ls-state-dot ls-state-dot--success"></span>
              <div><strong>{{ displayCount(data.running) }}</strong><span>Running</span></div>
            </router-link>
            <router-link :to="{ path: '/vm', query: routeQuery({ hypervisor: 'KVM', state: 'stopped' }) }" class="ls-vm-state">
              <span class="ls-state-dot"></span>
              <div><strong>{{ displayCount(data.stopped) }}</strong><span>Stopped</span></div>
            </router-link>
          </div>
          <div class="ls-panel-note">Counts are returned by CloudStack for KVM instances in the current authorized scope.</div>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="12">
        <a-card :bordered="false" class="ls-panel-card">
          <template #title>
            <div class="ls-card-title"><safety-certificate-outlined /> Service availability</div>
          </template>
          <div class="ls-service-list">
            <div v-for="service in serviceRows" :key="service.key" class="ls-service-row">
              <div>
                <strong>{{ service.label }}</strong>
                <span>{{ service.description }}</span>
              </div>
              <a-tag :color="service.color">{{ service.status }}</a-tag>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="ls-panel-card ls-activity-card">
      <template #title>
        <div class="ls-card-title"><schedule-outlined /> {{ $t('label.layersentry.recent.activity') }}</div>
      </template>
      <template #extra>
        <router-link v-if="hasApi('listEvents')" :to="{ path: '/event' }">{{ $t('label.view') }}</router-link>
      </template>
      <div v-if="loadingEvents" class="ls-empty-state"><a-spin /></div>
      <div v-else-if="!hasApi('listEvents')" class="ls-empty-state">Activity is not available to this role.</div>
      <a-alert v-else-if="eventsFailed" type="warning" show-icon :message="$t('label.layersentry.read.failed')" :description="$t('message.layersentry.read.failed')" />
      <div v-else-if="events.length === 0" class="ls-empty-state">{{ $t('label.layersentry.no.events') }}</div>
      <div v-else class="ls-activity-list">
        <router-link v-for="event in events" :key="event.id" :to="{ path: `/event/${event.id}` }" class="ls-activity-row">
          <span :class="['ls-event-dot', event.level === 'ERROR' ? 'ls-event-dot--error' : '']"></span>
          <div>
            <strong>{{ event.type || 'Activity' }}</strong>
            <small>{{ event.created ? $toLocaleDate(event.created) : '' }}</small>
            <span>{{ event.description || event.state || '' }}</span>
          </div>
        </router-link>
      </div>
    </a-card>
  </div>
</template>

<script>
import {
  ApartmentOutlined,
  BuildOutlined,
  CloudServerOutlined,
  DeploymentUnitOutlined,
  EnvironmentOutlined,
  HddOutlined,
  PictureOutlined,
  ReloadOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined
} from '@ant-design/icons-vue'
import { getAPI } from '@/api'
import { getLayersentryCapabilities, LAYERSENTRY_FEATURES } from '@/config/layersentryCapabilities'
import { getDashboardQuickActions, getDashboardRole } from './dashboardRole'
import { buildSelfServiceListParams, buildSelfServiceRouteQuery, countResponse } from './selfServiceDashboard'

export default {
  name: 'LayerSentrySelfServiceDashboard',
  components: {
    ApartmentOutlined,
    BuildOutlined,
    CloudServerOutlined,
    DeploymentUnitOutlined,
    EnvironmentOutlined,
    HddOutlined,
    PictureOutlined,
    ReloadOutlined,
    RocketOutlined,
    SafetyCertificateOutlined,
    ScheduleOutlined
  },
  data () {
    return {
      loading: false,
      loadingEvents: false,
      eventsFailed: false,
      partialFailures: [],
      data: {
        instances: null,
        running: null,
        stopped: null,
        volumes: null,
        snapshots: null,
        networks: null,
        vpcs: null,
        ips: null,
        templates: null,
        kubernetes: null,
        buckets: null,
        backups: null
      },
      events: []
    }
  },
  computed: {
    project () {
      return this.$store.getters.project || {}
    },
    dashboardRole () {
      return getDashboardRole(this.$store.getters.userInfo, this.$store.getters.apis, Boolean(this.project?.id))
    },
    dashboardRoleLabel () {
      return `label.layersentry.${this.dashboardRole}`
    },
    dashboardDescription () {
      if (this.dashboardRole === 'read-only') return 'Authorized inventory, service state and activity without mutation controls.'
      if (this.dashboardRole === 'department-admin') return 'Operate delegated department workloads and services without exposing physical infrastructure internals.'
      if (this.dashboardRole === 'project') return 'Operate resources in the active CloudStack project scope.'
      return 'Deploy and operate your authorized KVM workloads from a task-focused LayerSentry view.'
    },
    scopeLabel () {
      if (this.project?.id) return `Project: ${this.project.displaytext || this.project.name || this.project.id}`
      const account = this.$store.getters.userInfo?.account || this.$store.getters.userInfo?.accountname
      return account ? `Account: ${account}` : 'Current authorized account scope'
    },
    dashboardQuickActions () {
      if (this.dashboardRole === 'read-only') return []
      return getDashboardQuickActions(this.$store.getters.apis)
    },
    capabilities () {
      return getLayersentryCapabilities(this.$store.getters.apis, this.$config)
    },
    resourceCards () {
      const cards = []
      if (this.hasApi('listVirtualMachines')) cards.push({ key: 'vm', label: 'Virtual Machines', value: this.data.instances, icon: CloudServerOutlined, to: { path: '/vm', query: this.routeQuery({ hypervisor: 'KVM' }) } })
      if (this.hasApi('listVolumes')) cards.push({ key: 'volumes', label: 'Volumes', value: this.data.volumes, icon: HddOutlined, to: { path: '/volume', query: this.routeQuery() } })
      if (this.hasApi('listNetworks')) cards.push({ key: 'networks', label: 'Workload Networks', value: this.data.networks, icon: ApartmentOutlined, to: { path: '/guestnetwork', query: this.routeQuery() } })
      if (this.hasApi('listSnapshots')) cards.push({ key: 'snapshots', label: 'Recovery Points', value: this.data.snapshots, icon: BuildOutlined, to: { path: '/snapshot', query: this.routeQuery() }, detail: 'Volume snapshots' })
      if (this.hasApi('listVPCs')) cards.push({ key: 'vpcs', label: 'VPCs', value: this.data.vpcs, icon: DeploymentUnitOutlined, to: { path: '/vpc', query: this.routeQuery() } })
      if (this.hasApi('listPublicIpAddresses')) cards.push({ key: 'ips', label: 'Public IPs', value: this.data.ips, icon: EnvironmentOutlined, to: { path: '/publicip', query: this.routeQuery() } })
      if (this.hasApi('listTemplates')) cards.push({ key: 'images', label: 'OS Images', value: this.data.templates, icon: PictureOutlined, to: { path: '/template', query: this.routeQuery({ hypervisor: 'KVM' }) } })
      return cards
    },
    serviceRows () {
      const rows = []
      const nativeK8s = this.capabilities[LAYERSENTRY_FEATURES.NATIVE_KUBERNETES]
      if (nativeK8s?.visible) {
        rows.push({ key: 'kubernetes', label: 'Native Kubernetes', status: this.displayCount(this.data.kubernetes), color: 'blue', description: 'CloudStack Kubernetes service inventory.' })
      }
      const backup = this.capabilities[LAYERSENTRY_FEATURES.BACKUP]
      rows.push({
        key: 'backup',
        label: 'Backup & Recovery',
        status: backup?.visible ? this.displayCount(this.data.backups) : (backup?.enabled ? 'Prerequisites not ready' : 'Not enabled'),
        color: backup?.visible ? 'blue' : 'default',
        description: 'Availability follows feature policy, provider readiness and RBAC.'
      })
      const buckets = this.capabilities[LAYERSENTRY_FEATURES.BUCKETS]
      rows.push({
        key: 'buckets',
        label: 'Object Storage',
        status: buckets?.visible ? this.displayCount(this.data.buckets) : (buckets?.enabled ? 'Prerequisites not ready' : 'Not enabled'),
        color: buckets?.visible ? 'blue' : 'default',
        description: 'Buckets appear only when the provider is explicitly ready.'
      })
      return rows
    }
  },
  created () {
    this.refresh()
  },
  watch: {
    '$route' (to) {
      if (to.name === 'dashboard') this.refresh()
    }
  },
  methods: {
    hasApi (api) {
      return Object.prototype.hasOwnProperty.call(this.$store.getters.apis || {}, api)
    },
    listParams (extra = {}) {
      return buildSelfServiceListParams(this.project, extra)
    },
    routeQuery (extra = {}) {
      return buildSelfServiceRouteQuery(this.project, extra)
    },
    displayCount (value) {
      return value === null || value === undefined ? '—' : value
    },
    async guardedLoad (label, callback) {
      try {
        await callback()
      } catch (error) {
        if (!this.partialFailures.includes(label)) this.partialFailures.push(label)
        console.error(`LayerSentry self-service dashboard ${label} load failed`, error)
      }
    },
    async refresh () {
      if (this.loading) return
      this.loading = true
      this.partialFailures = []
      try {
        await Promise.all([
          this.guardedLoad('Virtual Machines', this.loadVirtualMachines),
          this.guardedLoad('Volumes', this.loadVolumes),
          this.guardedLoad('Networks', this.loadNetworks),
          this.guardedLoad('Recovery Points', this.loadSnapshots),
          this.guardedLoad('VPCs', this.loadVpcs),
          this.guardedLoad('Public IPs', this.loadIps),
          this.guardedLoad('OS Images', this.loadTemplates),
          this.guardedLoad('Services', this.loadServices),
          this.guardedLoad('Activity', this.loadEvents)
        ])
      } finally {
        this.loading = false
      }
    },
    async loadVirtualMachines () {
      this.data.instances = null
      this.data.running = null
      this.data.stopped = null
      if (!this.hasApi('listVirtualMachines')) return
      const base = { hypervisor: 'KVM', details: 'min' }
      const [all, running, stopped] = await Promise.all([
        getAPI('listVirtualMachines', this.listParams(base)),
        getAPI('listVirtualMachines', this.listParams({ ...base, state: 'Running' })),
        getAPI('listVirtualMachines', this.listParams({ ...base, state: 'Stopped' }))
      ])
      this.data.instances = countResponse(all, 'listvirtualmachinesresponse', 'virtualmachine')
      this.data.running = countResponse(running, 'listvirtualmachinesresponse', 'virtualmachine')
      this.data.stopped = countResponse(stopped, 'listvirtualmachinesresponse', 'virtualmachine')
    },
    async loadVolumes () {
      this.data.volumes = null
      if (!this.hasApi('listVolumes')) return
      const response = await getAPI('listVolumes', this.listParams())
      this.data.volumes = countResponse(response, 'listvolumesresponse', 'volume')
    },
    async loadSnapshots () {
      this.data.snapshots = null
      if (!this.hasApi('listSnapshots')) return
      const response = await getAPI('listSnapshots', this.listParams())
      this.data.snapshots = countResponse(response, 'listsnapshotsresponse', 'snapshot')
    },
    async loadNetworks () {
      this.data.networks = null
      if (!this.hasApi('listNetworks')) return
      const response = await getAPI('listNetworks', this.listParams())
      this.data.networks = countResponse(response, 'listnetworksresponse', 'network')
    },
    async loadVpcs () {
      this.data.vpcs = null
      if (!this.hasApi('listVPCs')) return
      const response = await getAPI('listVPCs', this.listParams())
      this.data.vpcs = countResponse(response, 'listvpcsresponse', 'vpc')
    },
    async loadIps () {
      this.data.ips = null
      if (!this.hasApi('listPublicIpAddresses')) return
      const response = await getAPI('listPublicIpAddresses', this.listParams())
      this.data.ips = countResponse(response, 'listpublicipaddressesresponse', 'publicipaddress')
    },
    async loadTemplates () {
      this.data.templates = null
      if (!this.hasApi('listTemplates')) return
      const response = await getAPI('listTemplates', this.listParams({ templatefilter: 'executable', hypervisor: 'KVM', isready: true }))
      this.data.templates = countResponse(response, 'listtemplatesresponse', 'template')
    },
    async loadServices () {
      const tasks = []
      this.data.kubernetes = null
      this.data.buckets = null
      this.data.backups = null
      if (this.capabilities[LAYERSENTRY_FEATURES.NATIVE_KUBERNETES]?.visible) {
        tasks.push(getAPI('listKubernetesClusters', this.listParams()).then(response => {
          this.data.kubernetes = countResponse(response, 'listkubernetesclustersresponse', 'kubernetescluster')
        }))
      }
      if (this.capabilities[LAYERSENTRY_FEATURES.BUCKETS]?.visible && this.hasApi('listBuckets')) {
        tasks.push(getAPI('listBuckets', this.listParams()).then(response => {
          this.data.buckets = countResponse(response, 'listbucketsresponse', 'bucket')
        }))
      }
      if (this.capabilities[LAYERSENTRY_FEATURES.BACKUP]?.visible && this.hasApi('listBackups')) {
        tasks.push(getAPI('listBackups', this.listParams()).then(response => {
          this.data.backups = countResponse(response, 'listbackupsresponse', 'backup')
        }))
      }
      await Promise.all(tasks)
    },
    async loadEvents () {
      this.events = []
      this.eventsFailed = false
      if (!this.hasApi('listEvents')) return
      this.loadingEvents = true
      try {
        const params = this.listParams()
        params.pagesize = 8
        const response = await getAPI('listEvents', params)
        this.events = response?.listeventsresponse?.event || []
      } catch (error) {
        this.eventsFailed = true
        throw error
      } finally {
        this.loadingEvents = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.ls-self-service-dashboard {
  max-width: 1480px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.ls-self-service-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
  padding: 20px;
  background: #fff;
  border: 1px solid #e4e7ec;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16, 24, 40, .06);

  h1 { margin: 2px 0 0; color: #101828; font-size: 28px; }
  p { max-width: 760px; margin: 8px 0 0; color: #667085; line-height: 1.55; }
}

.ls-eyebrow { color: #0f766e; font-size: 11px; font-weight: 700; letter-spacing: .12em; }
.ls-title-row, .ls-hero-actions, .ls-card-title { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.ls-hero-actions { justify-content: flex-end; }
.ls-scope { margin-top: 9px; color: #475467; font-size: 12px; font-weight: 600; }
.ls-dashboard-alert, .ls-secondary-row { margin-bottom: 16px; }
.ls-resource-link { display: block; height: 100%; color: inherit; }
.ls-resource-link:focus-visible .ls-resource-card { outline: 3px solid rgba(15, 118, 110, .35); outline-offset: 2px; }
.ls-resource-card, .ls-panel-card { height: 100%; border-radius: 10px; box-shadow: 0 1px 3px rgba(16, 24, 40, .08); }
.ls-resource-card { min-height: 155px; }
.ls-resource-card__icon { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; color: #0f766e; background: #f0fdfa; border-radius: 8px; font-size: 18px; }
.ls-resource-card__value { margin-top: 16px; color: #101828; font-size: 28px; font-weight: 700; line-height: 1; }
.ls-resource-card__label { margin-top: 7px; color: #344054; font-weight: 600; }
.ls-resource-card__detail, .ls-panel-note { margin-top: 4px; color: #667085; font-size: 12px; }
.ls-secondary-row { margin-top: 16px; }
.ls-card-title { color: #101828; font-weight: 650; }
.ls-vm-state-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.ls-vm-state { display: flex; align-items: center; gap: 10px; padding: 14px; color: inherit; background: #f9fafb; border: 1px solid #eaecf0; border-radius: 9px; }
.ls-vm-state div { display: grid; }
.ls-vm-state strong { color: #101828; font-size: 24px; }
.ls-vm-state span { color: #667085; }
.ls-state-dot { width: 10px; height: 10px; border-radius: 50%; background: #98a2b3; }
.ls-state-dot--success { background: #15803d; }
.ls-service-list { display: grid; }
.ls-service-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid #f2f4f7; }
.ls-service-row:last-child { border-bottom: 0; }
.ls-service-row > div { display: grid; gap: 2px; }
.ls-service-row span { color: #667085; font-size: 12px; }
.ls-activity-card { margin-top: 16px; min-height: 300px; }
.ls-activity-list { display: grid; }
.ls-activity-row { display: flex; gap: 11px; padding: 10px 4px; color: inherit; border-bottom: 1px solid #f2f4f7; }
.ls-activity-row:last-child { border-bottom: 0; }
.ls-activity-row > div { display: grid; min-width: 0; gap: 2px; }
.ls-activity-row strong { color: #344054; }
.ls-activity-row small { color: #98a2b3; }
.ls-activity-row span { color: #667085; font-size: 12px; overflow-wrap: anywhere; }
.ls-event-dot { flex: 0 0 auto; width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: #0f766e; }
.ls-event-dot--error { background: #b42318; }
.ls-empty-state { min-height: 180px; display: flex; align-items: center; justify-content: center; color: #667085; text-align: center; }

@media (max-width: 800px) {
  .ls-self-service-hero { flex-direction: column; }
  .ls-hero-actions { width: 100%; justify-content: flex-start; }
  .ls-vm-state-grid { grid-template-columns: 1fr; }
}
</style>
