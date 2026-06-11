<template>
	<div v-if="showChat" class="fixed bottom-20 right-4 z-[1000] sm:right-[calc(50%-12rem+1rem)]">
		<div
			v-if="isOpen"
			class="mb-3 flex h-[32rem] max-h-[calc(100vh-8rem)] w-[calc(100vw-2rem)] flex-col overflow-hidden rounded bg-white shadow-2xl sm:w-80"
		>
			<div class="flex items-center justify-between border-b px-4 py-3">
				<div>
					<div class="text-base font-semibold text-gray-900">{{ __("FOBS AI") }}</div>
					<div class="text-xs text-gray-500">{{ activeSessionLabel }}</div>
				</div>
				<div class="flex items-center gap-1">
					<Button variant="ghost" class="!px-2" @click="startNewSession">
						<template #prefix>
							<FeatherIcon name="plus" class="w-4" />
						</template>
					</Button>
					<Button variant="ghost" class="!px-2" @click="isOpen = false">
						<template #prefix>
							<FeatherIcon name="x" class="w-4" />
						</template>
					</Button>
				</div>
			</div>

			<div ref="messagesContainer" class="flex-1 overflow-y-auto bg-gray-50 p-3">
				<div v-if="!messages.length" class="flex h-full items-center justify-center text-center text-sm text-gray-500">
					{{ __("Start a new chat with FOBS AI.") }}
				</div>

				<div v-else class="flex flex-col gap-3">
					<div
						v-for="message in messages"
						:key="message.id"
						class="flex"
						:class="message.role === 'user' ? 'justify-end' : 'justify-start'"
					>
						<div
							class="max-w-[85%] rounded px-3 py-2 text-sm leading-5"
							:class="message.role === 'user' ? 'bg-gray-900 text-white' : 'bg-white text-gray-800 shadow-sm'"
						>
							{{ message.content }}
						</div>
					</div>
				</div>
			</div>

			<form class="flex gap-2 border-t bg-white p-3" @submit.prevent="sendMessage">
				<textarea
					v-model="draftMessage"
					class="min-h-10 flex-1 resize-none rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900"
					:placeholder="__('Ask FOBS AI...')"
					rows="1"
					@keydown.enter.exact.prevent="sendMessage"
				/>
				<Button
					variant="solid"
					class="self-end"
					:loading="chat.loading"
					:disabled="chat.loading || !draftMessage.trim()"
					@click="sendMessage"
				>
					<template #prefix>
						<FeatherIcon name="send" class="w-4" />
					</template>
				</Button>
			</form>
		</div>

		<Button variant="solid" class="h-12 w-12 rounded-full shadow-lg" @click="isOpen = !isOpen">
			<template #prefix>
				<FeatherIcon :name="isOpen ? 'x' : 'message-circle'" class="w-5" />
			</template>
		</Button>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { Button, FeatherIcon, createResource, toast } from "frappe-ui"

const __ = inject("$translate")
const route = useRoute()

const isOpen = ref(false)
const activeSession = ref("")
const draftMessage = ref("")
const messages = ref([])
const messagesContainer = ref(null)

const hiddenRoutes = new Set(["Login", "ForgotPassword", "InvalidEmployee"])

const showChat = computed(() => !hiddenRoutes.has(route.name))

const activeSessionLabel = computed(() => {
	return activeSession.value ? __("Chat session active") : __("New chat session")
})

const chat = createResource({
	url: "hrms.api.fobs_ai.send_message",
	method: "POST",
})

function startNewSession() {
	activeSession.value = ""
	messages.value = []
	draftMessage.value = ""
	isOpen.value = true
}

function sendMessage() {
	const content = draftMessage.value.trim()
	if (!content || chat.loading) return

	draftMessage.value = ""
	messages.value.push({
		id: `user-${Date.now()}`,
		role: "user",
		content,
	})
	scrollToBottom()

	chat.submit(
		{
			message: content,
			session: activeSession.value || undefined,
		},
		{
			onSuccess(data) {
				activeSession.value = data.session
				messages.value.push({
					id: `assistant-${Date.now()}`,
					role: "assistant",
					content: data.reply,
				})
				scrollToBottom()
			},
			onError(error) {
				messages.value.push({
					id: `assistant-error-${Date.now()}`,
					role: "assistant",
					content: error.messages?.[0] || __("FOBS AI is not available right now."),
				})
				toast({
					title: __("Error"),
					text: error.messages?.[0] || __("FOBS AI is not available right now."),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
				scrollToBottom()
			},
		}
	)
}

function scrollToBottom() {
	nextTick(() => {
		if (!messagesContainer.value) return
		messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
	})
}

watch(showChat, (value) => {
	if (!value) isOpen.value = false
})
</script>
