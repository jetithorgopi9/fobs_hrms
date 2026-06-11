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
							class="flex items-center justify-between border rounded p-3"
						>
							<div>
								<div class="text-sm font-medium text-gray-900">
									{{ breakType.break_name }}
								</div>
								<div class="text-xs text-gray-500">
									{{ __("Next break gap: {0} minutes", [breakType.minimum_gap_after_previous_break_minutes || 45]) }}
								</div>
							</div>
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
</template>

<script setup>
import { computed, inject } from "vue"
import { createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const status = createResource({
	url: "hrms.api.break_management.get_break_status",
	auto: true,
	cache: "hrms:break-management-status",
})

const activeBreakLabel = computed(() => {
	if (!status.data?.active_break) return __("None")
	return __("{0} since {1}", [
		status.data.active_break.break_type,
		formatDateTime(status.data.active_break.start_time),
	])
})

function formatLogTime(log) {
	if (!log?.time) return __("Not available")
	const label = log.log_type ? `${log.log_type} · ` : ""
	return `${label}${formatDateTime(log.time)}`
}

function formatDateTime(value) {
	if (!value) return __("Not available")
	return dayjs(value).format("D MMM YYYY, hh:mm A")
}
</script>
