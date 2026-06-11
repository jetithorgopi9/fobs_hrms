<template>
	<BaseLayout :pageTitle="__('Break Management')">
		<template #body>
			<div class="flex flex-col mt-7 mb-7 p-4 gap-4">
				<div class="flex flex-col bg-white rounded p-4 gap-3">
					<div class="text-base font-semibold text-gray-900">
						{{ __("Today") }}
					</div>

					<div class="text-sm text-gray-700">
						<span class="font-medium">{{ __("First Punch") }}: </span>
						<span>{{ formatLogTime(status.data?.first_checkin) }}</span>
					</div>

					<div class="text-sm text-gray-700">
						<span class="font-medium">{{ __("Latest Punch") }}: </span>
						<span>{{ formatLogTime(status.data?.last_checkout) }}</span>
					</div>

					<div class="text-sm text-gray-700">
						<span class="font-medium">{{ __("Active Break") }}: </span>
						<span>{{ activeBreakLabel }}</span>
					</div>

					<Button
						v-if="activeBreak"
						variant="solid"
						class="w-full py-5 text-base"
						@click="openActiveBreakModal"
					>
						<template #prefix>
							<FeatherIcon name="clock" class="w-4" />
						</template>
						{{ __("View Running Break") }}
					</Button>
				</div>

				<div class="flex flex-col bg-white rounded p-4 gap-3">
					<div class="text-base font-semibold text-gray-900">
						{{ __("Available Breaks") }}
					</div>

					<div v-if="status.loading" class="text-sm text-gray-500">
						{{ __("Loading...") }}
					</div>

					<div v-else-if="!status.data?.can_start_break" class="text-sm text-gray-500">
						{{ status.data?.start_block_reason || __("Break cannot be started right now.") }}
					</div>

					<div v-else class="flex flex-col gap-2">
						<div
							v-for="breakType in status.data?.break_types || []"
							:key="breakType.name"
							class="flex items-center justify-between border rounded p-3 gap-3"
						>
							<div class="min-w-0">
								<div class="text-sm font-medium text-gray-900">
									{{ breakType.break_name }}
								</div>
								<div class="text-xs text-gray-500">
									{{ __("Next break gap: {0} minutes", [breakType.minimum_gap_after_previous_break_minutes || 45]) }}
								</div>
							</div>
							<Button
								variant="solid"
								class="shrink-0"
								:loading="startBreak.loading && selectedBreakType === breakType.name"
								:disabled="startBreak.loading || stopBreak.loading"
								@click="startSelectedBreak(breakType)"
							>
								{{ __("Start") }}
							</Button>
						</div>
					</div>
				</div>

				<div class="flex flex-col bg-white rounded p-4 gap-3">
					<div class="text-base font-semibold text-gray-900">
						{{ __("Today Break History") }}
					</div>

					<div v-if="!status.data?.history?.length" class="text-sm text-gray-500">
						{{ __("No breaks recorded today.") }}
					</div>

					<div
						v-for="breakLog in status.data?.history || []"
						:key="breakLog.name"
						class="border rounded p-3 text-sm text-gray-700"
					>
						<div class="font-medium text-gray-900">{{ breakLog.break_type }}</div>
						<div>{{ __("Started") }}: {{ formatDateTime(breakLog.start_time) }}</div>
						<div>{{ __("Stopped") }}: {{ formatDateTime(breakLog.stop_time) }}</div>
						<div>{{ __("Status") }}: {{ breakLog.status }}</div>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>

	<ion-modal
		:is-open="isBreakModalOpen"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
		:backdrop-dismiss="false"
		@didDismiss="handleBreakModalDismiss"
	>
		<div class="h-120 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5">
			<div class="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
				<FeatherIcon name="coffee" class="h-7 w-7 text-gray-700" />
			</div>

			<div class="flex flex-col items-center gap-1 text-center">
				<div class="text-sm font-medium text-gray-500">
					{{ __("Break Running") }}
				</div>
				<div class="text-3xl font-bold text-gray-900 tabular-nums">
					{{ activeBreakElapsed }}
				</div>
				<div class="text-base font-medium text-gray-900">
					{{ activeBreak?.break_type }}
				</div>
				<div class="text-sm text-gray-500">
					{{ __("Started at {0}", [formatTime(activeBreak?.start_time)]) }}
				</div>
			</div>

			<Button
				variant="solid"
				class="w-full py-5 text-base"
				:loading="stopBreak.loading"
				:disabled="stopBreak.loading"
				@click="stopActiveBreak"
			>
				{{ __("Stop Break") }}
			</Button>
		</div>
	</ion-modal>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { IonModal } from "@ionic/vue"
import { Button, FeatherIcon, createResource, toast } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const currentTime = ref(dayjs())
const isBreakModalOpen = ref(false)
const isStoppingBreak = ref(false)
const selectedBreakType = ref("")
let timer = null

const status = createResource({
	url: "hrms.api.break_management.get_break_status",
	auto: true,
})

const startBreak = createResource({
	url: "hrms.api.break_management.start_break",
	method: "POST",
})

const stopBreak = createResource({
	url: "hrms.api.break_management.stop_break",
	method: "POST",
})

const activeBreak = computed(() => status.data?.active_break)

const activeBreakLabel = computed(() => {
	if (!activeBreak.value) return __("None")
	return __("{0} since {1}", [
		activeBreak.value.break_type,
		formatDateTime(activeBreak.value.start_time),
	])
})

const activeBreakElapsed = computed(() => {
	if (!activeBreak.value?.start_time) return "00:00:00"

	const elapsedSeconds = Math.max(
		0,
		currentTime.value.diff(dayjs(activeBreak.value.start_time), "second")
	)

	return formatElapsedTime(elapsedSeconds)
})

function startSelectedBreak(breakType) {
	selectedBreakType.value = breakType.name
	startBreak.submit(
		{ break_type: breakType.name },
		{
			onSuccess() {
				toast({
					title: __("Success"),
					text: __("Break started."),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
				selectedBreakType.value = ""
				status.reload()
				openActiveBreakModal()
			},
			onError(error) {
				selectedBreakType.value = ""
				showError(error)
			},
		}
	)
}

function stopActiveBreak() {
	isStoppingBreak.value = true
	stopBreak.submit(
		{},
		{
			onSuccess() {
				toast({
					title: __("Success"),
					text: __("Break stopped."),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
				status.reload()
				isBreakModalOpen.value = false
				window.setTimeout(() => {
					isStoppingBreak.value = false
				}, 500)
			},
			onError(error) {
				isStoppingBreak.value = false
				showError(error)
			},
		}
	)
}

function openActiveBreakModal() {
	if (!activeBreak.value) return
	isBreakModalOpen.value = true
}

function handleBreakModalDismiss() {
	isBreakModalOpen.value = false

	if (activeBreak.value && !isStoppingBreak.value) {
		window.setTimeout(openActiveBreakModal, 0)
	}
}

function formatLogTime(log) {
	if (!log?.time) return __("Not available")
	const label = log.log_type ? `${log.log_type} · ` : ""
	return `${label}${formatDateTime(log.time)}`
}

function formatDateTime(value) {
	if (!value) return __("Not available")
	return dayjs(value).format("D MMM YYYY, hh:mm A")
}

function formatTime(value) {
	if (!value) return __("Not available")
	return dayjs(value).format("hh:mm A")
}

function formatElapsedTime(seconds) {
	const hours = Math.floor(seconds / 3600)
	const minutes = Math.floor((seconds % 3600) / 60)
	const remainingSeconds = seconds % 60

	return [hours, minutes, remainingSeconds]
		.map((part) => String(part).padStart(2, "0"))
		.join(":")
}

function showError(error) {
	const message = error.messages?.[0] || __("Break action failed.")

	toast({
		title: __("Error"),
		text: message,
		icon: "alert-circle",
		position: "bottom-center",
		iconClasses: "text-red-500",
	})
}

watch(
	activeBreak,
	(value) => {
		if (value) {
			openActiveBreakModal()
		}
	},
	{ immediate: true }
)

onMounted(() => {
	timer = window.setInterval(() => {
		currentTime.value = dayjs()
	}, 1000)
})

onBeforeUnmount(() => {
	if (timer) window.clearInterval(timer)
})
</script>
