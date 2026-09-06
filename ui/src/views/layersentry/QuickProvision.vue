<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements. See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership. The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License. You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing,
 software distributed under the License is distributed on an
 "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 KIND, either express or implied. See the License for the
 specific language governing permissions and limitations
 under the License.
-->

<template>
  <div class="ls-quick-provision">
    <div class="ls-quick-hero">
      <div>
        <div class="ls-eyebrow">LAYERSENTRY PRIVATE CLOUD</div>
        <h1>Quick Provision</h1>
        <p>
          Provision a KVM virtual machine from one page. LayerSentry resolves ownership,
          Site, compute, storage and workload-network intent while CloudStack remains
          authoritative for placement, lifecycle and asynchronous operations.
        </p>
      </div>
      <div class="ls-hero-tags">
        <a-tag color="green">KVM only</a-tag>
        <a-tag>Native CloudStack APIs</a-tag>
      </div>
    </div>

    <a-alert
      v-if="loadError"
      type="error"
      show-icon
      :message="loadError"
      class="ls-alert" />

    <a-alert
      v-if="preflight.message"
      :type="preflight.type"
      show-icon
      :message="preflight.message"
      class="ls-alert" />

    <a-alert
      v-if="operation.message"
      :type="operation.type"
      show-icon
      class="ls-alert">
      <template #message>{{ operation.message }}</template>
      <template #description>
        <div v-if="operation.jobId" class="ls-operation-id">CloudStack job: {{ operation.jobId }}</div>
        <ul v-if="operation.details.length" class="ls-issue-list">
          <li v-for="detail in operation.details" :key="detail">{{ detail }}</li>
        </ul>
        <div v-if="operation.password" class="ls-password-row">
          <span>Generated VM password:</span>
          <a-typography-text code :copyable="{ text: operation.password }">{{ operation.password }}</a-typography-text>
        </div>
        <a-button v-if="operation.vmId" size="small" class="ls-open-vm" @click="openProvisionedVm">
          Open virtual machine
        </a-button>
      </template>
    </a-alert>

    <div class="ls-stage-strip" role="status" aria-live="polite">
      <div
        v-for="stage in operationStages"
        :key="stage.key"
        class="ls-stage"
        :class="stageClass(stage.key)">
        <span class="ls-stage__dot" aria-hidden="true"></span>
        <span>{{ stage.label }}</span>
      </div>
    </div>

    <a-row :gutter="16">
      <a-col :xs="24" :xl="17">
        <a-form layout="vertical" :model="form" @finish="deploy">
          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><environment-outlined /> Ownership &amp; Site</span>
            </template>

            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="VM name" name="name" :rules="[{ required: true, message: 'Enter a VM name' }]">
                  <a-input v-model:value.trim="form.name" placeholder="app-prod-01" autocomplete="off" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Site" name="zoneid" :rules="[{ required: true, message: 'Select a Site' }]">
                  <a-select
                    v-model:value="form.zoneid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.zones"
                    :options="zoneOptions"
                    placeholder="Select Site"
                    @change="onZoneChange" />
                </a-form-item>
              </a-col>
            </a-row>

            <div v-if="canChooseOwnership" class="ls-owner-target">
              <div class="ls-owner-target__heading">
                <div>
                  <strong>Administrative deployment target</strong>
                  <div class="ls-muted">This changes only the native CloudStack account/domain/project scope. Server-side authorization remains authoritative.</div>
                </div>
              </div>
              <a-radio-group v-model:value="form.scopeMode" button-style="solid" @change="onScopeModeChange">
                <a-radio-button value="current">Current context</a-radio-button>
                <a-radio-button v-if="canTargetDepartment" value="department">Department / Account</a-radio-button>
                <a-radio-button v-if="canTargetProject" value="project">Project</a-radio-button>
              </a-radio-group>

              <a-row v-if="form.scopeMode === 'department'" :gutter="16" class="ls-owner-fields">
                <a-col :xs="24" :md="12">
                  <a-form-item label="Department boundary">
                    <a-select
                      v-model:value="form.targetdomainid"
                      show-search
                      option-filter-prop="label"
                      :loading="loading.domains"
                      :options="domainOptions"
                      placeholder="Select domain / department boundary"
                      @change="onTargetDomainChange" />
                  </a-form-item>
                </a-col>
                <a-col :xs="24" :md="12">
                  <a-form-item label="Target Account">
                    <a-select
                      v-model:value="form.targetaccount"
                      show-search
                      option-filter-prop="label"
                      :loading="loading.accounts"
                      :options="accountOptions"
                      :disabled="!form.targetdomainid"
                      placeholder="Select target Account"
                      @change="onTargetOwnerChange" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row v-if="form.scopeMode === 'project'" :gutter="16" class="ls-owner-fields">
                <a-col :xs="24">
                  <a-form-item label="Target Project">
                    <a-select
                      v-model:value="form.targetprojectid"
                      show-search
                      option-filter-prop="label"
                      :loading="loading.projects"
                      :options="projectOptions"
                      placeholder="Select target Project"
                      @change="onTargetOwnerChange" />
                  </a-form-item>
                </a-col>
              </a-row>
            </div>

            <div class="ls-scope-strip">
              <div>
                <span class="ls-scope-strip__label">Deployment scope</span>
                <strong>{{ deploymentScopeLabel }}</strong>
              </div>
              <a-tag :color="deploymentScopeTagColor">{{ deploymentScopeTag }}</a-tag>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><cloud-server-outlined /> Compute</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="OS Image" name="templateid" :rules="[{ required: true, message: 'Select an OS Image' }]">
                  <a-select
                    v-model:value="form.templateid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.templates"
                    :options="templateOptions"
                    :disabled="!kvmSiteReady || !scopeComplete"
                    placeholder="Select KVM OS Image"
                    @change="onTemplateChange" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Compute Profile" name="serviceofferingid" :rules="[{ required: true, message: 'Select a Compute Profile' }]">
                  <a-select
                    v-model:value="form.serviceofferingid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.compute"
                    :options="computeOptions"
                    :disabled="!kvmSiteReady || !scopeComplete"
                    placeholder="Select Compute Profile"
                    @change="onComputeProfileChange" />
                </a-form-item>
              </a-col>
              <a-col v-if="canListSshKeyPairs" :xs="24" :md="12">
                <a-form-item label="SSH key pair (optional)">
                  <a-select
                    v-model:value="form.keypair"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.keys"
                    :options="sshKeyOptions"
                    :disabled="!kvmSiteReady || !scopeComplete"
                    placeholder="Use image/default authentication" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-alert
              v-if="selectedComputeProfile?.iscustomized"
              type="info"
              show-icon
              class="ls-inline-alert"
              message="This Compute Profile is custom-sized. CPU, CPU speed and memory are required by the native deployment API." />
            <a-row v-if="selectedComputeProfile?.iscustomized" :gutter="16">
              <a-col :xs="24" :md="8">
                <a-form-item label="vCPU">
                  <a-input-number v-model:value="form.cpunumber" :min="1" :precision="0" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="CPU speed (MHz)">
                  <a-input-number v-model:value="form.cpuspeed" :min="1" :precision="0" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="Memory (MiB)">
                  <a-input-number v-model:value="form.memory" :min="1" :precision="0" style="width: 100%" />
                </a-form-item>
              </a-col>
            </a-row>

            <div class="ls-inline-state ls-inline-state--wrap">
              <a-tag color="green">KVM</a-tag>
              <a-tag :color="preflightTagColor(preflight.site)">Site: {{ preflightTagLabel(preflight.site) }}</a-tag>
              <a-tag :color="preflightTagColor(preflight.image)">OS Image: {{ preflightTagLabel(preflight.image) }}</a-tag>
              <span>Non-KVM hypervisors remain preserved upstream but are not presented by the LayerSentry customer profile.</span>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><database-outlined /> Storage</span>
            </template>

            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="Root Storage Profile override (optional)">
                  <a-select
                    v-model:value="form.rootdiskofferingid"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.storage"
                    :options="rootStorageOptions"
                    :disabled="!kvmSiteReady || !scopeComplete || selectedComputeProfile?.diskofferingstrictness"
                    placeholder="Use Compute Profile / image default" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Root disk size (GiB, optional)">
                  <a-input-number
                    v-model:value="form.rootdisksize"
                    :min="1"
                    :precision="0"
                    :disabled="!kvmSiteReady || !scopeComplete"
                    style="width: 100%"
                    placeholder="Use image/profile default" />
                </a-form-item>
              </a-col>
            </a-row>

            <div class="ls-subsection-header">
              <div>
                <strong>New data volumes</strong>
                <div class="ls-muted">Create one or more CloudStack-managed data disks with deterministic device IDs.</div>
              </div>
              <a-button
                v-if="storageProfiles.length > 0"
                :disabled="!kvmSiteReady || !scopeComplete"
                @click="addDataVolume">
                <plus-outlined /> Add data volume
              </a-button>
            </div>

            <div v-if="form.dataVolumes.length === 0" class="ls-empty-row">No new data volumes selected.</div>

            <div v-for="(volume, index) in form.dataVolumes" :key="volume.key" class="ls-data-volume">
              <div class="ls-data-volume__header">
                <strong>Data volume {{ index + 1 }}</strong>
                <a-button type="text" danger :aria-label="`Remove data volume ${index + 1}`" @click="removeDataVolume(index)">
                  <delete-outlined />
                </a-button>
              </div>
              <a-row :gutter="12">
                <a-col :xs="24" :md="12">
                  <a-form-item label="Storage Profile">
                    <a-select
                      v-model:value="volume.diskofferingid"
                      show-search
                      option-filter-prop="label"
                      :options="storageOptions"
                      placeholder="Select Storage Profile"
                      @change="onDataVolumeProfileChange(volume)" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomized" :xs="24" :md="12">
                  <a-form-item label="Size (GiB)">
                    <a-input-number v-model:value="volume.size" :min="1" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomizediops" :xs="24" :md="12">
                  <a-form-item label="Minimum IOPS">
                    <a-input-number v-model:value="volume.miniops" :min="0" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomizediops" :xs="24" :md="12">
                  <a-form-item label="Maximum IOPS">
                    <a-input-number v-model:value="volume.maxiops" :min="0" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>
              <div v-if="selectedDataOffering(volume)" class="ls-volume-facts">
                <span>Device ID {{ index + 1 }}</span>
                <span>{{ selectedDataOffering(volume).storagetype || 'Storage policy managed' }}</span>
                <span v-if="selectedDataOffering(volume).provisioningtype">{{ selectedDataOffering(volume).provisioningtype }} provisioning</span>
              </div>
            </div>

            <div v-if="canAttachExistingVolumes" class="ls-existing-volumes">
              <a-form-item label="Attach existing detached data volumes (optional)">
                <a-select
                  v-model:value="form.existingvolumeids"
                  mode="multiple"
                  allow-clear
                  show-search
                  option-filter-prop="label"
                  :loading="loading.volumes"
                  :options="existingVolumeOptions"
                  :disabled="!kvmSiteReady || !scopeComplete"
                  placeholder="Select detached Ready volumes" />
              </a-form-item>
              <div class="ls-muted">Existing volumes are attached after VM creation. If an attachment fails, the VM remains created and LayerSentry reports a partial result instead of rolling back or hiding the failure.</div>
            </div>

            <div class="ls-callout">
              <database-outlined />
              <div>
                <strong>Storage backend is policy-driven.</strong>
                <span>
                  NFS, iSCSI/FC SAN, Ceph, LINSTOR and other certified backends are presented as Storage Profiles.
                  Tenant users never receive SAN target credentials or raw LUN controls.
                </span>
              </div>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><apartment-outlined /> Network</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="VPC (optional)">
                  <a-select
                    v-model:value="form.vpcid"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.vpcs"
                    :options="vpcOptions"
                    :disabled="!kvmSiteReady || !scopeComplete || !canListVpcs"
                    placeholder="Site networks / no VPC"
                    @change="loadNetworks" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Primary Network Blueprint" name="networkid" :rules="networkRules">
                  <a-select
                    v-model:value="form.networkid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.networks"
                    :options="networkOptions"
                    :disabled="!kvmSiteReady || !scopeComplete || selectedZoneNetworkType === 'Basic'"
                    :placeholder="selectedZoneNetworkType === 'Basic' ? 'Managed by the Site' : 'Select primary workload network'"
                    @change="onPrimaryNetworkChange" />
                </a-form-item>
              </a-col>
              <a-col v-if="selectedZoneNetworkType !== 'Basic'" :xs="24" :md="12">
                <a-form-item label="Additional workload networks (optional)">
                  <a-select
                    v-model:value="form.additionalnetworkids"
                    mode="multiple"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.networks"
                    :options="additionalNetworkOptions"
                    :disabled="!form.networkid"
                    placeholder="Attach additional networks" />
                </a-form-item>
              </a-col>
              <a-col v-if="canOverrideIp && selectedZoneNetworkType !== 'Basic'" :xs="24" :md="12">
                <a-form-item label="Primary private IP override (optional)">
                  <a-input v-model:value.trim="form.ipaddress" placeholder="Automatic from destination pool" autocomplete="off" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-descriptions v-if="selectedNetwork" size="small" :column="networkDescriptionColumns" bordered>
              <a-descriptions-item label="Resolved network">{{ selectedNetwork.name }}</a-descriptions-item>
              <a-descriptions-item label="VLAN policy">{{ resolvedVlan }}</a-descriptions-item>
              <a-descriptions-item label="CIDR">{{ selectedNetwork.cidr || 'Provider managed' }}</a-descriptions-item>
              <a-descriptions-item label="Gateway">{{ selectedNetwork.gateway || 'Provider managed' }}</a-descriptions-item>
              <a-descriptions-item label="DNS">{{ resolvedDns }}</a-descriptions-item>
              <a-descriptions-item label="Network domain">{{ selectedNetwork.networkdomain || 'Site policy' }}</a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><safety-certificate-outlined /> Availability &amp; Protection</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <div class="ls-feature-row">
                  <div>
                    <strong>VM HA request</strong>
                    <div class="ls-muted">CloudStack remains authoritative for actual HA eligibility and recovery behavior.</div>
                  </div>
                  <a-tag :color="selectedComputeProfile?.offerha ? 'blue' : 'default'">
                    {{ selectedComputeProfile?.offerha ? 'Requested by Compute Profile' : 'Not requested' }}
                  </a-tag>
                </div>
              </a-col>
              <a-col :xs="24" :md="12">
                <div class="ls-feature-row">
                  <div>
                    <strong>DR</strong>
                    <div class="ls-muted">No browser-side DR intent is invented. A recovery Site/network/IP plan will appear only when the server-side DR contract provides real mapping data.</div>
                  </div>
                  <a-tag :color="drCapabilityColor">{{ drCapabilityLabel }}</a-tag>
                </div>
              </a-col>
            </a-row>

            <div v-if="canUseBackup" class="ls-protection-select">
              <a-form-item label="Backup Protection Plan (optional)">
                <a-select
                  v-model:value="form.backupofferingid"
                  allow-clear
                  show-search
                  option-filter-prop="label"
                  :loading="loading.backup"
                  :options="backupOfferingOptions"
                  :disabled="!kvmSiteReady || !scopeComplete"
                  placeholder="Do not assign backup protection" />
              </a-form-item>
              <div class="ls-muted">The VM is created first. The selected CloudStack Backup Offering is then assigned through the native asynchronous backup API.</div>
            </div>
            <a-alert
              v-else
              type="info"
              show-icon
              :message="backupCapabilityMessage" />

            <a-alert
              type="info"
              show-icon
              class="ls-protection-truth"
              message="Quick Provision never marks a VM Protected, HA or DR Ready from UI intent alone. Those states require confirmed API/provider evidence." />
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><check-circle-outlined /> Review, Preflight &amp; Deploy</span>
            </template>

            <a-alert v-if="blockingIssues.length" type="warning" show-icon class="ls-review-alert">
              <template #message>Resolve {{ blockingIssues.length }} blocking item{{ blockingIssues.length === 1 ? '' : 's' }} before deployment.</template>
              <template #description>
                <ul class="ls-issue-list">
                  <li v-for="issue in blockingIssues" :key="issue">{{ issue }}</li>
                </ul>
              </template>
            </a-alert>
            <a-alert
              v-else
              type="success"
              show-icon
              class="ls-review-alert"
              message="Core provisioning plan is valid. Run preflight again immediately before deployment." />

            <div class="ls-review-controls">
              <a-checkbox v-model:checked="form.startvm">Start VM after provisioning</a-checkbox>
              <div class="ls-actions">
                <a-button :disabled="deploying" @click="$router.back()">Cancel</a-button>
                <a-button :loading="loading.preflight" :disabled="!form.zoneid || deploying" @click="runPreflight">
                  <check-circle-outlined /> Run preflight
                </a-button>
                <a-button type="primary" html-type="submit" :loading="deploying" :disabled="!readyToDeploy || deploying">
                  <rocket-outlined /> Provision VM
                </a-button>
              </div>
            </div>
          </a-card>
        </a-form>
      </a-col>

      <a-col :xs="24" :xl="7">
        <a-affix :offset-top="76">
          <a-card class="ls-plan-card" :bordered="false" title="Resolved plan">
            <div class="ls-plan-row"><span>Scope</span><strong>{{ deploymentScopeLabel }}</strong></div>
            <div class="ls-plan-row"><span>Site</span><strong>{{ selectedZone?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Hypervisor</span><strong>KVM</strong></div>
            <div class="ls-plan-row"><span>OS Image</span><strong>{{ selectedTemplate?.displaytext || selectedTemplate?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Compute</span><strong>{{ selectedComputeProfile?.name || 'Not selected' }}</strong></div>
            <div v-if="selectedComputeProfile?.iscustomized" class="ls-plan-row"><span>Custom compute</span><strong>{{ form.cpunumber || '?' }} vCPU / {{ form.memory || '?' }} MiB</strong></div>
            <div class="ls-plan-row"><span>Root storage</span><strong>{{ selectedRootStorageProfile?.displaytext || selectedRootStorageProfile?.name || 'Default policy' }}</strong></div>
            <div class="ls-plan-row"><span>Root size</span><strong>{{ form.rootdisksize ? `${form.rootdisksize} GiB` : 'Default' }}</strong></div>
            <div class="ls-plan-row"><span>New data volumes</span><strong>{{ form.dataVolumes.length }}</strong></div>
            <div class="ls-plan-row"><span>Existing volumes</span><strong>{{ form.existingvolumeids.length }}</strong></div>
            <div class="ls-plan-row"><span>VPC</span><strong>{{ selectedVpc?.name || 'None' }}</strong></div>
            <div class="ls-plan-row"><span>Primary network</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : (selectedNetwork?.name || 'Not selected') }}</strong></div>
            <div class="ls-plan-row"><span>Additional networks</span><strong>{{ form.additionalnetworkids.length }}</strong></div>
            <div class="ls-plan-row"><span>Private IP</span><strong>{{ form.ipaddress || 'Automatic' }}</strong></div>
            <div class="ls-plan-row"><span>VLAN</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : resolvedVlan }}</strong></div>
            <div class="ls-plan-row"><span>Backup plan</span><strong>{{ selectedBackupOffering?.name || 'None' }}</strong></div>
            <a-divider />
            <div class="ls-preflight">
              <check-circle-outlined v-if="readyToDeploy" class="ls-ok" />
              <info-circle-outlined v-else />
              <span>{{ readyToDeploy ? 'KVM and OS Image preflight are current and the provisioning plan has no blocking inputs.' : 'Complete the required inputs and preflight checks.' }}</span>
            </div>
          </a-card>
        </a-affix>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EnvironmentOutlined,
  InfoCircleOutlined,
  PlusOutlined,
  RocketOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons-vue'
import { getAPI, postAPI } from '@/api'
import { checkKvmImage, checkKvmSite } from '@/config/kvmProvisioning'
import { getLayersentryCapabilities, LAYERSENTRY_FEATURES } from '@/config/layersentryCapabilities'
import {
  buildQuickProvisionBackupAssignmentParams,
  buildQuickProvisionDeployParams,
  buildQuickProvisionScopeParams,
  canChooseQuickProvisionOwnership,
  normaliseAdditionalNetworks,
  QUICK_PROVISION_SCOPE_MODES,
  quickProvisionBlockingIssues
} from './quickProvision'

const ASYNC_JOB_POLL_MS = 2000
const ASYNC_JOB_TIMEOUT_MS = 30 * 60 * 1000

export default {
  name: 'LayersentryQuickProvision',
  components: {
    ApartmentOutlined,
    CheckCircleOutlined,
    CloudServerOutlined,
    DatabaseOutlined,
    DeleteOutlined,
    EnvironmentOutlined,
    InfoCircleOutlined,
    PlusOutlined,
    RocketOutlined,
    SafetyCertificateOutlined
  },
  data () {
    return {
      form: {
        name: '',
        scopeMode: QUICK_PROVISION_SCOPE_MODES.CURRENT,
        targetdomainid: undefined,
        targetaccount: undefined,
        targetprojectid: undefined,
        zoneid: undefined,
        templateid: undefined,
        serviceofferingid: undefined,
        cpunumber: undefined,
        cpuspeed: undefined,
        memory: undefined,
        keypair: undefined,
        rootdiskofferingid: undefined,
        rootdisksize: undefined,
        dataVolumes: [],
        existingvolumeids: [],
        vpcid: undefined,
        networkid: undefined,
        additionalnetworkids: [],
        ipaddress: '',
        backupofferingid: undefined,
        startvm: true
      },
      zones: [],
      domains: [],
      accounts: [],
      projects: [],
      templates: [],
      computeProfiles: [],
      storageProfiles: [],
      sshKeyPairs: [],
      existingVolumes: [],
      vpcs: [],
      networks: [],
      backupOfferings: [],
      loading: {
        zones: false,
        domains: false,
        accounts: false,
        projects: false,
        templates: false,
        compute: false,
        storage: false,
        keys: false,
        volumes: false,
        vpcs: false,
        networks: false,
        backup: false,
        preflight: false
      },
      deploying: false,
      loadError: '',
      nextDataVolumeKey: 0,
      preflight: {
        site: 'idle',
        image: 'idle',
        type: 'info',
        message: ''
      },
      operation: {
        stage: 'idle',
        type: 'info',
        message: '',
        details: [],
        vmId: undefined,
        jobId: undefined,
        password: undefined
      }
    }
  },
  computed: {
    userInfo () {
      return this.$store.getters.userInfo || {}
    },
    roleType () {
      return this.userInfo.roletype
    },
    capabilities () {
      return getLayersentryCapabilities(this.$store.getters.apis, this.$config)
    },
    activeProjectId () {
      return this.$store.getters.project?.id || undefined
    },
    canChooseOwnership () {
      return canChooseQuickProvisionOwnership(this.roleType) && (this.canTargetDepartment || this.canTargetProject)
    },
    canTargetDepartment () {
      return canChooseQuickProvisionOwnership(this.roleType) && Boolean(this.$store.getters.apis?.listDomains && this.$store.getters.apis?.listAccounts)
    },
    canTargetProject () {
      return canChooseQuickProvisionOwnership(this.roleType) && Boolean(this.$store.getters.apis?.listProjects)
    },
    scopeComplete () {
      if (!this.canChooseOwnership || this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.CURRENT) return true
      if (this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) return Boolean(this.form.targetdomainid && this.form.targetaccount)
      if (this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.PROJECT) return Boolean(this.form.targetprojectid)
      return false
    },
    scopeParams () {
      return buildQuickProvisionScopeParams({
        form: this.form,
        currentProjectId: this.activeProjectId,
        roleType: this.roleType
      })
    },
    deploymentScopeLabel () {
      if (this.canChooseOwnership && this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.PROJECT) {
        const project = this.projects.find(item => item.id === this.form.targetprojectid)
        return project?.displaytext || project?.name || 'Select target Project'
      }
      if (this.canChooseOwnership && this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) {
        if (!this.form.targetaccount) return 'Select target Account'
        const account = this.accounts.find(item => item.name === this.form.targetaccount)
        const domain = this.domains.find(item => item.id === this.form.targetdomainid)
        return `${account?.name || this.form.targetaccount}${domain?.name ? ` / ${domain.name}` : ''}`
      }
      if (this.activeProjectId) return this.$store.getters.project?.displaytext || this.$store.getters.project?.name || this.activeProjectId
      return this.userInfo.account || this.userInfo.accountname || 'Current Account'
    },
    deploymentScopeTag () {
      if (this.canChooseOwnership && this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.PROJECT) return 'Project'
      if (this.canChooseOwnership && this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) return 'Account'
      return this.activeProjectId ? 'Project' : 'Current Account'
    },
    deploymentScopeTagColor () {
      return this.deploymentScopeTag === 'Project' ? 'blue' : 'default'
    },
    canListVpcs () {
      return Boolean(this.$store.getters.apis?.listVPCs)
    },
    canOverrideIp () {
      return ['Admin', 'DomainAdmin'].includes(this.roleType)
    },
    canListSshKeyPairs () {
      return Boolean(this.$store.getters.apis?.listSSHKeyPairs)
    },
    canAttachExistingVolumes () {
      return Boolean(this.$store.getters.apis?.listVolumes && this.$store.getters.apis?.attachVolume)
    },
    backupCapability () {
      return this.capabilities[LAYERSENTRY_FEATURES.BACKUP]
    },
    drCapability () {
      return this.capabilities[LAYERSENTRY_FEATURES.DR]
    },
    canUseBackup () {
      return Boolean(this.backupCapability?.visible && this.$store.getters.apis?.listBackupOfferings && this.$store.getters.apis?.assignVirtualMachineToBackupOffering)
    },
    backupCapabilityMessage () {
      if (this.backupCapability?.enabled && !this.backupCapability?.ready) return 'Backup is enabled by policy but the provider is not certified Ready for self-service assignment.'
      if (this.backupCapability?.reason === 'missing-api') return 'Backup provider prerequisites exist, but the required CloudStack backup APIs are not available to this role.'
      return 'Backup Protection Plan selection is not enabled for this deployment context.'
    },
    drCapabilityLabel () {
      if (this.drCapability?.visible) return 'Provider contract required'
      if (this.drCapability?.enabled) return 'Prerequisites not ready'
      return 'Not enabled'
    },
    drCapabilityColor () {
      if (this.drCapability?.visible) return 'blue'
      if (this.drCapability?.enabled) return 'orange'
      return 'default'
    },
    kvmSiteReady () {
      return this.preflight.site === 'ready'
    },
    imageReady () {
      return this.preflight.image === 'ready'
    },
    selectedZone () {
      return this.zones.find(item => item.id === this.form.zoneid)
    },
    selectedZoneNetworkType () {
      return this.selectedZone?.networktype || ''
    },
    selectedTemplate () {
      return this.templates.find(item => item.id === this.form.templateid)
    },
    selectedComputeProfile () {
      return this.computeProfiles.find(item => item.id === this.form.serviceofferingid)
    },
    selectedRootStorageProfile () {
      return this.storageProfiles.find(item => item.id === this.form.rootdiskofferingid)
    },
    selectedVpc () {
      return this.vpcs.find(item => item.id === this.form.vpcid)
    },
    selectedNetwork () {
      return this.networks.find(item => item.id === this.form.networkid)
    },
    selectedBackupOffering () {
      return this.backupOfferings.find(item => item.id === this.form.backupofferingid)
    },
    zoneOptions () {
      return this.zones.map(item => ({ label: item.name, value: item.id }))
    },
    domainOptions () {
      return this.domains.map(item => ({ label: item.path || item.name, value: item.id }))
    },
    accountOptions () {
      return this.accounts.map(item => ({ label: item.name, value: item.name }))
    },
    projectOptions () {
      return this.projects.map(item => ({
        label: `${item.displaytext || item.name}${item.account ? ` — ${item.account}` : ''}`,
        value: item.id
      }))
    },
    templateOptions () {
      return this.templates.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    computeOptions () {
      return this.computeProfiles.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    storageOptions () {
      return this.storageProfiles.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    rootStorageOptions () {
      return this.storageProfiles.filter(item => !item.iscustomizediops).map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    sshKeyOptions () {
      return this.sshKeyPairs.map(item => ({ label: item.name, value: item.name }))
    },
    existingVolumeOptions () {
      return this.existingVolumes.map(item => ({
        label: `${item.name || item.id}${item.size ? ` — ${this.formatGiB(item.size)}` : ''}`,
        value: item.id
      }))
    },
    vpcOptions () {
      return this.vpcs.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    networkOptions () {
      return this.networks.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    additionalNetworkOptions () {
      return this.networkOptions.filter(option => option.value !== this.form.networkid)
    },
    backupOfferingOptions () {
      return this.backupOfferings.map(item => ({
        label: `${item.name}${item.provider ? ` — ${item.provider}` : ''}`,
        value: item.id
      }))
    },
    resolvedVlan () {
      if (!this.selectedNetwork) return 'Automatic'
      if (this.roleType !== 'Admin') return 'Automatic by Network Blueprint'
      const raw = this.selectedNetwork.vlan || this.selectedNetwork.broadcasturi
      if (!raw) return 'Automatic by Network Blueprint'
      return String(raw).replace(/^vlan:\/\//i, '')
    },
    resolvedDns () {
      if (!this.selectedNetwork) return 'Site policy'
      return [this.selectedNetwork.dns1, this.selectedNetwork.dns2].filter(Boolean).join(', ') || 'Site policy'
    },
    networkRules () {
      if (!this.form.zoneid || this.selectedZoneNetworkType === 'Basic') return []
      return [{ required: true, message: 'Select a Network Blueprint' }]
    },
    blockingIssues () {
      return quickProvisionBlockingIssues({
        form: this.form,
        roleType: this.roleType,
        networkType: this.selectedZoneNetworkType,
        storageProfiles: this.storageProfiles,
        computeProfiles: this.computeProfiles,
        existingVolumes: this.existingVolumes,
        backupReady: this.canUseBackup,
        kvmSiteReady: this.kvmSiteReady,
        imageReady: this.imageReady
      })
    },
    readyToDeploy () {
      return this.scopeComplete && this.blockingIssues.length === 0 && !this.loading.preflight
    },
    networkDescriptionColumns () {
      return window.innerWidth < 900 ? 1 : 2
    },
    operationStages () {
      return [
        { key: 'validate', label: 'Validate' },
        { key: 'deploy', label: 'Deploy VM' },
        { key: 'storage', label: 'Finalize storage' },
        { key: 'protection', label: 'Configure protection' },
        { key: 'complete', label: 'Complete' }
      ]
    }
  },
  mounted () {
    this.initialise()
  },
  methods: {
    responseItems (response, responseKey, itemKey) {
      return response?.[responseKey]?.[itemKey] || []
    },
    selectOnlyOption (field, items) {
      if (items.length === 1) this.form[field] = items[0].id
    },
    errorMessage (error, fallback) {
      const key = error?.message
      if (key && key.startsWith('message.')) return this.$t(key)
      return error?.message || fallback
    },
    formatGiB (bytes) {
      const value = Number(bytes)
      if (!Number.isFinite(value) || value <= 0) return 'Unknown size'
      return `${Math.round(value / (1024 ** 3) * 10) / 10} GiB`
    },
    stageClass (stage) {
      const order = ['validate', 'deploy', 'storage', 'protection', 'complete']
      const current = order.indexOf(this.operation.stage)
      const index = order.indexOf(stage)
      if (this.operation.stage === 'idle') return ''
      if (index < current || (stage === 'complete' && this.operation.stage === 'complete')) return 'ls-stage--done'
      if (index === current) return 'ls-stage--active'
      return ''
    },
    preflightTagColor (state) {
      if (state === 'ready') return 'green'
      if (state === 'checking') return 'blue'
      if (state === 'error') return 'red'
      return 'default'
    },
    preflightTagLabel (state) {
      if (state === 'ready') return 'Verified'
      if (state === 'checking') return 'Checking'
      if (state === 'error') return 'Blocked'
      return 'Not checked'
    },
    async initialise () {
      await Promise.all([this.loadOwnershipInventory(), this.loadZones()])
    },
    async loadOwnershipInventory () {
      const tasks = []
      if (this.canTargetDepartment) tasks.push(this.loadDomains())
      if (this.canTargetProject) tasks.push(this.loadProjects())
      await Promise.all(tasks)
    },
    async loadDomains () {
      this.loading.domains = true
      try {
        const response = await getAPI('listDomains', { listall: true, details: 'min' })
        this.domains = this.responseItems(response, 'listdomainsresponse', 'domain')
      } catch (error) {
        console.warn('Administrative domain inventory is not available.', error)
        this.domains = []
      } finally {
        this.loading.domains = false
      }
    },
    async loadAccounts () {
      this.accounts = []
      if (!this.form.targetdomainid || !this.canTargetDepartment) return
      this.loading.accounts = true
      try {
        const response = await getAPI('listAccounts', {
          domainid: this.form.targetdomainid,
          listall: true,
          state: 'enabled',
          details: 'min'
        })
        this.accounts = this.responseItems(response, 'listaccountsresponse', 'account')
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.accounts = false
      }
    },
    async loadProjects () {
      this.loading.projects = true
      try {
        const response = await getAPI('listProjects', { listall: true })
        this.projects = this.responseItems(response, 'listprojectsresponse', 'project')
          .filter(item => !item.state || String(item.state).toLowerCase() === 'active')
      } catch (error) {
        console.warn('Administrative project inventory is not available.', error)
        this.projects = []
      } finally {
        this.loading.projects = false
      }
    },
    async onScopeModeChange () {
      this.form.targetaccount = undefined
      this.form.targetprojectid = undefined
      if (this.form.scopeMode === QUICK_PROVISION_SCOPE_MODES.DEPARTMENT) {
        const currentDomainId = this.userInfo.domainid
        this.form.targetdomainid = this.domains.some(item => item.id === currentDomainId) ? currentDomainId : undefined
        if (this.form.targetdomainid) await this.loadAccounts()
      } else {
        this.form.targetdomainid = undefined
        this.accounts = []
      }
      await this.refreshForOwnershipChange()
    },
    async onTargetDomainChange () {
      this.form.targetaccount = undefined
      await this.loadAccounts()
      await this.refreshForOwnershipChange()
    },
    async onTargetOwnerChange () {
      await this.refreshForOwnershipChange()
    },
    async refreshForOwnershipChange () {
      this.resetScopedDependencies()
      if (!this.form.zoneid || !this.scopeComplete) return
      await this.onZoneChange()
    },
    async loadZones () {
      this.loading.zones = true
      this.loadError = ''
      try {
        const response = await getAPI('listZones', { showicon: true })
        this.zones = this.responseItems(response, 'listzonesresponse', 'zone')
        if (this.zones.length === 1) {
          this.form.zoneid = this.zones[0].id
          await this.onZoneChange()
        }
      } catch (error) {
        this.loadError = 'Unable to load Sites. Check CloudStack API access and try again.'
        console.error(error)
      } finally {
        this.loading.zones = false
      }
    },
    resetScopedDependencies () {
      this.form.templateid = undefined
      this.form.serviceofferingid = undefined
      this.form.cpunumber = undefined
      this.form.cpuspeed = undefined
      this.form.memory = undefined
      this.form.keypair = undefined
      this.form.rootdiskofferingid = undefined
      this.form.rootdisksize = undefined
      this.form.dataVolumes = []
      this.form.existingvolumeids = []
      this.form.vpcid = undefined
      this.form.networkid = undefined
      this.form.additionalnetworkids = []
      this.form.ipaddress = ''
      this.form.backupofferingid = undefined
      this.templates = []
      this.computeProfiles = []
      this.storageProfiles = []
      this.sshKeyPairs = []
      this.existingVolumes = []
      this.vpcs = []
      this.networks = []
      this.backupOfferings = []
      this.preflight.image = 'idle'
      this.preflight.message = ''
    },
    async validateSiteKvm () {
      if (!this.form.zoneid) {
        this.preflight.site = 'idle'
        return false
      }
      const zoneId = this.form.zoneid
      this.preflight.site = 'checking'
      try {
        await checkKvmSite(getAPI, zoneId)
        if (zoneId !== this.form.zoneid) return false
        this.preflight.site = 'ready'
        return true
      } catch (error) {
        if (zoneId !== this.form.zoneid) return false
        this.preflight.site = 'error'
        this.loadError = this.errorMessage(error, 'KVM availability could not be verified for this Site.')
        return false
      }
    },
    async onZoneChange () {
      this.resetScopedDependencies()
      this.loadError = ''
      if (!this.form.zoneid) {
        this.preflight.site = 'idle'
        return
      }
      const siteReady = await this.validateSiteKvm()
      if (!siteReady || !this.scopeComplete) return
      const zoneId = this.form.zoneid
      await Promise.all([
        this.loadTemplates(),
        this.loadComputeProfiles(),
        this.loadStorageProfiles(),
        this.loadSshKeyPairs(),
        this.loadExistingVolumes(),
        this.loadVpcs(),
        this.loadBackupOfferings()
      ])
      if (zoneId !== this.form.zoneid) return
      await this.loadNetworks()
      if (this.form.templateid) await this.validateSelectedImage()
    },
    async loadTemplates () {
      this.loading.templates = true
      try {
        const response = await getAPI('listTemplates', {
          templatefilter: 'executable',
          zoneid: this.form.zoneid,
          hypervisor: 'KVM',
          isready: true,
          listall: true,
          showicon: true,
          details: 'all',
          ...this.scopeParams
        })
        const templates = this.responseItems(response, 'listtemplatesresponse', 'template')
        this.templates = templates.filter(item => item.hypervisor === 'KVM')
        this.selectOnlyOption('templateid', this.templates)
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.templates = false
      }
    },
    async loadComputeProfiles () {
      this.loading.compute = true
      try {
        const response = await getAPI('listServiceOfferings', {
          zoneid: this.form.zoneid,
          issystem: false,
          listall: true,
          ...this.scopeParams
        })
        this.computeProfiles = this.responseItems(response, 'listserviceofferingsresponse', 'serviceoffering')
        this.selectOnlyOption('serviceofferingid', this.computeProfiles)
        if (this.form.serviceofferingid) this.onComputeProfileChange()
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.compute = false
      }
    },
    onComputeProfileChange () {
      this.form.cpunumber = undefined
      this.form.cpuspeed = undefined
      this.form.memory = undefined
      const offering = this.selectedComputeProfile
      if (!offering?.iscustomized) return
      if (Number(offering.cpunumber) > 0) this.form.cpunumber = Number(offering.cpunumber)
      if (Number(offering.cpuspeed) > 0) this.form.cpuspeed = Number(offering.cpuspeed)
      if (Number(offering.memory) > 0) this.form.memory = Number(offering.memory)
    },
    async loadStorageProfiles () {
      this.loading.storage = true
      try {
        const response = await getAPI('listDiskOfferings', {
          zoneid: this.form.zoneid,
          listall: true,
          ...this.scopeParams
        })
        this.storageProfiles = this.responseItems(response, 'listdiskofferingsresponse', 'diskoffering')
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.storage = false
      }
    },
    async loadSshKeyPairs () {
      this.sshKeyPairs = []
      if (!this.canListSshKeyPairs) return
      this.loading.keys = true
      try {
        const response = await getAPI('listSSHKeyPairs', { listall: true, ...this.scopeParams })
        this.sshKeyPairs = this.responseItems(response, 'listsshkeypairsresponse', 'sshkeypair')
      } catch (error) {
        console.warn('SSH key inventory is not available for this scope.', error)
      } finally {
        this.loading.keys = false
      }
    },
    async loadExistingVolumes () {
      this.existingVolumes = []
      if (!this.canAttachExistingVolumes) return
      this.loading.volumes = true
      try {
        const response = await getAPI('listVolumes', {
          zoneid: this.form.zoneid,
          listall: true,
          ...this.scopeParams
        })
        this.existingVolumes = this.responseItems(response, 'listvolumesresponse', 'volume')
          .filter(item => String(item.type || '').toUpperCase() === 'DATADISK')
          .filter(item => !item.virtualmachineid)
          .filter(item => !item.state || String(item.state).toLowerCase() === 'ready')
      } catch (error) {
        console.warn('Detached volume inventory is not available for this scope.', error)
      } finally {
        this.loading.volumes = false
      }
    },
    async loadVpcs () {
      this.vpcs = []
      if (!this.canListVpcs) return
      this.loading.vpcs = true
      try {
        const response = await getAPI('listVPCs', {
          zoneid: this.form.zoneid,
          listall: true,
          ...this.scopeParams
        })
        this.vpcs = this.responseItems(response, 'listvpcsresponse', 'vpc')
      } catch (error) {
        console.warn('VPC inventory is not available for this role or target scope.', error)
      } finally {
        this.loading.vpcs = false
      }
    },
    async loadNetworks () {
      this.form.networkid = undefined
      this.form.additionalnetworkids = []
      this.form.ipaddress = ''
      this.networks = []
      if (!this.form.zoneid || !this.scopeComplete || this.selectedZoneNetworkType === 'Basic') return
      this.loading.networks = true
      try {
        const params = {
          zoneid: this.form.zoneid,
          canusefordeploy: true,
          listall: true,
          showicon: true,
          ...this.scopeParams
        }
        if (this.form.vpcid) params.vpcid = this.form.vpcid
        const response = await getAPI('listNetworks', params)
        this.networks = this.responseItems(response, 'listnetworksresponse', 'network')
        this.selectOnlyOption('networkid', this.networks)
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.networks = false
      }
    },
    async loadBackupOfferings () {
      this.backupOfferings = []
      if (!this.canUseBackup) return
      this.loading.backup = true
      try {
        const response = await getAPI('listBackupOfferings', { zoneid: this.form.zoneid })
        this.backupOfferings = this.responseItems(response, 'listbackupofferingsresponse', 'backupoffering')
      } catch (error) {
        console.warn('Backup Protection Plans are not available for this Site.', error)
      } finally {
        this.loading.backup = false
      }
    },
    onPrimaryNetworkChange () {
      this.form.additionalnetworkids = normaliseAdditionalNetworks(this.form.networkid, this.form.additionalnetworkids)
      this.form.ipaddress = ''
    },
    async onTemplateChange () {
      this.preflight.image = 'idle'
      this.preflight.message = ''
      await this.validateSelectedImage()
    },
    async validateSelectedImage () {
      if (!this.form.zoneid || !this.form.templateid || !this.scopeComplete) {
        this.preflight.image = 'idle'
        return false
      }
      const zoneId = this.form.zoneid
      const templateId = this.form.templateid
      this.preflight.image = 'checking'
      try {
        await checkKvmImage(getAPI, zoneId, 'templateid', templateId, this.scopeParams)
        if (zoneId !== this.form.zoneid || templateId !== this.form.templateid) return false
        this.preflight.image = 'ready'
        return true
      } catch (error) {
        if (zoneId !== this.form.zoneid || templateId !== this.form.templateid) return false
        this.preflight.image = 'error'
        this.preflight.type = 'error'
        this.preflight.message = this.errorMessage(error, 'The selected OS Image failed the KVM preflight.')
        return false
      }
    },
    addDataVolume () {
      this.nextDataVolumeKey += 1
      this.form.dataVolumes.push({
        key: this.nextDataVolumeKey,
        diskofferingid: undefined,
        size: undefined,
        miniops: undefined,
        maxiops: undefined
      })
    },
    removeDataVolume (index) {
      this.form.dataVolumes.splice(index, 1)
    },
    selectedDataOffering (volume) {
      return this.storageProfiles.find(item => item.id === volume?.diskofferingid)
    },
    onDataVolumeProfileChange (volume) {
      const offering = this.selectedDataOffering(volume)
      if (!offering?.iscustomized) volume.size = undefined
      if (!offering?.iscustomizediops) {
        volume.miniops = undefined
        volume.maxiops = undefined
      }
    },
    buildDeployParams () {
      return buildQuickProvisionDeployParams({
        form: this.form,
        networkType: this.selectedZoneNetworkType,
        storageProfiles: this.storageProfiles,
        computeProfiles: this.computeProfiles,
        scopeParams: this.scopeParams
      })
    },
    async runPreflight () {
      if (this.loading.preflight || this.deploying) return false
      this.loading.preflight = true
      this.operation.stage = 'validate'
      this.preflight.message = ''
      this.preflight.type = 'info'
      try {
        const siteReady = await this.validateSiteKvm()
        if (siteReady && this.scopeComplete) await this.validateSelectedImage()
        const issues = this.blockingIssues
        if (issues.length > 0) {
          this.preflight.type = 'warning'
          this.preflight.message = `Preflight is blocked by ${issues.length} unresolved item${issues.length === 1 ? '' : 's'}.`
          return false
        }
        this.preflight.type = 'success'
        this.preflight.message = 'Preflight passed for the current ownership scope, Site, KVM OS Image and provisioning inputs.'
        return true
      } finally {
        this.loading.preflight = false
      }
    },
    sleep (milliseconds) {
      return new Promise(resolve => window.setTimeout(resolve, milliseconds))
    },
    async waitForAsyncJob (jobId, activity) {
      const deadline = Date.now() + ASYNC_JOB_TIMEOUT_MS
      while (Date.now() < deadline) {
        const response = await getAPI('queryAsyncJobResult', { jobid: jobId })
        const job = response?.queryasyncjobresultresponse || {}
        const status = Number(job.jobstatus || 0)
        if (status === 1) return job
        if (status === 2) {
          const error = new Error(job?.jobresult?.errortext || `${activity} failed.`)
          error.jobId = jobId
          error.errorCode = job?.jobresult?.errorcode
          throw error
        }
        await this.sleep(ASYNC_JOB_POLL_MS)
      }
      const error = new Error(`${activity} was submitted but its final state was not confirmed in this browser session. Check Activity using job ${jobId}.`)
      error.jobId = jobId
      error.pending = true
      throw error
    },
    async attachExistingVolumes (vmId) {
      const warnings = []
      for (const volumeId of this.form.existingvolumeids) {
        const volume = this.existingVolumes.find(item => item.id === volumeId)
        try {
          const response = await postAPI('attachVolume', { id: volumeId, virtualmachineid: vmId })
          const jobId = response?.attachvolumeresponse?.jobid
          if (!jobId) throw new Error('CloudStack did not return an async job ID for volume attachment.')
          await this.waitForAsyncJob(jobId, `Attaching ${volume?.name || volumeId}`)
        } catch (error) {
          warnings.push(`${volume?.name || volumeId}: ${this.errorMessage(error, 'Volume attachment was not confirmed.')}`)
        }
      }
      return warnings
    },
    async assignBackupProtection (vmId) {
      if (!this.form.backupofferingid) return []
      const params = buildQuickProvisionBackupAssignmentParams(vmId, this.form.backupofferingid)
      if (!params) return ['Backup Protection Plan selection could not be resolved after VM creation.']
      try {
        const response = await postAPI('assignVirtualMachineToBackupOffering', params)
        const jobId = response?.assignvirtualmachinetobackupofferingresponse?.jobid
        if (!jobId) throw new Error('CloudStack did not return an async job ID for backup assignment.')
        await this.waitForAsyncJob(jobId, 'Backup Protection Plan assignment')
        return []
      } catch (error) {
        return [this.errorMessage(error, 'Backup Protection Plan assignment was not confirmed.')]
      }
    },
    resetOperation () {
      this.operation = {
        stage: 'validate',
        type: 'info',
        message: '',
        details: [],
        vmId: undefined,
        jobId: undefined,
        password: undefined
      }
    },
    async deploy () {
      if (this.deploying) return
      this.resetOperation()
      const passed = await this.runPreflight()
      if (!passed) return

      this.deploying = true
      this.operation.stage = 'deploy'
      this.operation.type = 'info'
      this.operation.message = `Provisioning ${this.form.name} through CloudStack.`
      try {
        const response = await postAPI('deployVirtualMachine', this.buildDeployParams())
        const jobId = response?.deployvirtualmachineresponse?.jobid
        if (!jobId) throw new Error('CloudStack did not return an async job ID for VM deployment.')
        this.operation.jobId = jobId

        const completed = await this.waitForAsyncJob(jobId, 'Virtual machine deployment')
        const vm = completed?.jobresult?.virtualmachine
        if (!vm?.id) {
          const error = new Error(`CloudStack completed deployment job ${jobId}, but the response did not contain a virtual machine ID. Check Activity before retrying.`)
          error.pending = true
          error.jobId = jobId
          throw error
        }

        this.operation.vmId = vm.id
        this.operation.password = vm.password || undefined
        const warnings = []

        if (this.form.existingvolumeids.length > 0) {
          this.operation.stage = 'storage'
          this.operation.message = 'Virtual machine created. Finalizing existing volume attachments.'
          warnings.push(...await this.attachExistingVolumes(vm.id))
        }

        if (this.form.backupofferingid) {
          this.operation.stage = 'protection'
          this.operation.message = 'Virtual machine created. Configuring backup protection.'
          const protectionWarnings = await this.assignBackupProtection(vm.id)
          warnings.push(...protectionWarnings.map(item => `Backup: ${item}`))
        }

        this.operation.stage = 'complete'
        const vmName = vm.displayname || vm.name || this.form.name
        if (warnings.length > 0) {
          this.operation.type = 'warning'
          this.operation.message = `${vmName} was created, but one or more post-deploy steps need attention.`
          this.operation.details = warnings
          this.$notification.warning({
            message: 'Virtual machine created with partial completion',
            description: 'The VM exists. Review the post-deploy warnings before retrying only the affected action.'
          })
        } else {
          this.operation.type = 'success'
          this.operation.message = `${vmName} was created and every selected post-deploy step was confirmed.`
          this.operation.details = []
          this.$notification.success({
            message: 'Virtual machine provisioned',
            description: `${vmName} was created through the native CloudStack KVM workflow.`
          })
        }
      } catch (error) {
        if (error?.pending) {
          this.operation.type = 'warning'
          this.operation.message = 'Deployment was submitted, but final VM state is not confirmed. Do not submit a duplicate deployment until Activity is checked.'
          this.operation.details = [this.errorMessage(error, 'CloudStack deployment state is not confirmed.')]
          this.operation.jobId = error.jobId || this.operation.jobId
        } else {
          this.operation.type = 'error'
          this.operation.message = 'Virtual machine deployment failed before a confirmed VM result was returned.'
          this.operation.details = [this.errorMessage(error, 'CloudStack rejected or failed the deployment.')]
          this.$notifyError(error)
        }
      } finally {
        this.deploying = false
      }
    },
    openProvisionedVm () {
      if (this.operation.vmId) this.$router.push({ path: `/vm/${this.operation.vmId}` })
    }
  }
}
</script>

<style scoped>
.ls-quick-provision {
  max-width: 1500px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.ls-quick-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding: 8px 4px 22px;
}

.ls-quick-hero h1 {
  margin: 2px 0 8px;
  font-size: 30px;
  line-height: 1.2;
}

.ls-quick-hero p {
  max-width: 860px;
  margin: 0;
  color: rgba(0, 0, 0, 0.56);
  font-size: 15px;
  line-height: 1.65;
}

.ls-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  opacity: 0.58;
}

.ls-hero-tags,
.ls-inline-state,
.ls-actions,
.ls-volume-facts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ls-hero-tags {
  justify-content: flex-end;
}

.ls-alert,
.ls-section-card,
.ls-stage-strip {
  margin-bottom: 16px;
}

.ls-section-card,
.ls-plan-card {
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 10px 26px rgba(0, 0, 0, 0.03);
}

.ls-section-title {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-weight: 650;
}

.ls-stage-strip {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #eaecf0;
  border-radius: 10px;
  background: #fff;
}

.ls-stage {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: #98a2b3;
  font-size: 12px;
}

.ls-stage__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border: 1px solid currentColor;
  border-radius: 50%;
}

.ls-stage--active {
  color: #1677ff;
  font-weight: 600;
}

.ls-stage--done {
  color: #389e0d;
}

.ls-stage--done .ls-stage__dot,
.ls-stage--active .ls-stage__dot {
  background: currentColor;
}

.ls-owner-target,
.ls-existing-volumes,
.ls-protection-select {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 9px;
  background: #fcfcfd;
}

.ls-owner-target__heading {
  margin-bottom: 10px;
}

.ls-owner-fields {
  margin-top: 12px;
}

.ls-scope-strip,
.ls-subsection-header,
.ls-data-volume__header,
.ls-review-controls,
.ls-feature-row,
.ls-password-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ls-scope-strip {
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #eaecf0;
  border-radius: 8px;
}

.ls-scope-strip__label {
  display: block;
  margin-bottom: 2px;
  color: #667085;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ls-inline-state {
  align-items: center;
  color: rgba(0, 0, 0, 0.55);
  font-size: 13px;
}

.ls-inline-alert,
.ls-protection-truth {
  margin-bottom: 14px;
}

.ls-subsection-header {
  margin: 8px 0 12px;
}

.ls-empty-row {
  margin-bottom: 14px;
  padding: 16px;
  color: #667085;
  background: #f9fafb;
  border: 1px dashed #d0d5dd;
  border-radius: 9px;
  text-align: center;
}

.ls-data-volume {
  margin-bottom: 12px;
  padding: 12px 14px 4px;
  border: 1px solid #e4e7ec;
  border-radius: 9px;
  background: #fff;
}

.ls-data-volume__header {
  margin-bottom: 2px;
}

.ls-volume-facts {
  margin: -2px 0 10px;
  color: #667085;
  font-size: 12px;
}

.ls-callout {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 9px;
  background: rgba(0, 0, 0, 0.018);
}

.ls-callout > div > span {
  display: block;
  margin-top: 3px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.5;
}

.ls-feature-row {
  min-height: 86px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 9px;
}

.ls-muted {
  margin-top: 3px;
  color: rgba(0, 0, 0, 0.52);
  font-size: 12px;
  line-height: 1.45;
}

.ls-review-alert {
  margin-bottom: 14px;
}

.ls-issue-list {
  margin: 8px 0 0 18px;
  padding: 0;
}

.ls-operation-id {
  margin-bottom: 6px;
  font-family: monospace;
  overflow-wrap: anywhere;
}

.ls-password-row {
  justify-content: flex-start;
  margin-top: 10px;
  flex-wrap: wrap;
}

.ls-open-vm {
  margin-top: 10px;
}

.ls-review-controls {
  align-items: flex-end;
  flex-wrap: wrap;
}

.ls-actions {
  justify-content: flex-end;
  margin-top: 10px;
}

.ls-plan-row {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.ls-plan-row span {
  color: rgba(0, 0, 0, 0.48);
}

.ls-plan-row strong {
  text-align: right;
  overflow-wrap: anywhere;
}

.ls-preflight {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  color: rgba(0, 0, 0, 0.62);
}

.ls-ok {
  color: #389e0d;
}

@media (max-width: 1199px) {
  .ls-plan-card {
    margin-top: 4px;
  }
}

@media (max-width: 767px) {
  .ls-quick-hero,
  .ls-review-controls,
  .ls-subsection-header {
    flex-direction: column;
    align-items: stretch;
  }

  .ls-hero-tags {
    justify-content: flex-start;
  }

  .ls-stage-strip {
    grid-template-columns: 1fr;
  }

  .ls-quick-hero h1 {
    font-size: 26px;
  }

  .ls-actions {
    justify-content: stretch;
  }

  .ls-actions .ant-btn {
    flex: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto !important;
  }
}
</style>
