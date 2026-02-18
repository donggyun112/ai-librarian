import {
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { GrokIcon } from "@/components/icons/grok";
import {
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ChainOfThoughtPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";
import {
  ArrowUpIcon,
  ChevronDownIcon,
  CopyIcon,
  Pencil1Icon,
  ReloadIcon,
} from "@radix-ui/react-icons";
import {
  ArrowDownIcon,
  BrainIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  Mic,
  Moon,
  Paperclip,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import type { FC } from "react";
import { useEffect, useRef, useState } from "react";

const escapeSelectorValue = (value: string): string => {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/g, "\\$&");
};

const alignUserMessageByIdToViewportTop = (messageId: string): boolean => {
  const viewport = document.querySelector<HTMLElement>(".aui-thread-viewport");
  if (!viewport) return false;

  const selector = `.aui-user-message-root[data-message-id="${escapeSelectorValue(messageId)}"]`;
  const target = viewport.querySelector<HTMLElement>(selector);
  if (!target) return false;

  target.scrollIntoView({
    behavior: "auto",
    block: "start",
    inline: "nearest",
  });

  const viewportTop = viewport.getBoundingClientRect().top;
  const targetTop = target.getBoundingClientRect().top;
  const delta = targetTop - viewportTop;
  if (Math.abs(delta) < 1) return true;

  viewport.scrollTop += delta;
  return true;
};

const scheduleAlignUserMessageByIdToTop = (messageId: string) => {
  let tries = 0;

  const tick = () => {
    alignUserMessageByIdToViewportTop(messageId);
    tries += 1;
    if (tries < 28) {
      requestAnimationFrame(tick);
    }
  };

  requestAnimationFrame(tick);
  window.setTimeout(() => {
    alignUserMessageByIdToViewportTop(messageId);
  }, 180);
  window.setTimeout(() => {
    alignUserMessageByIdToViewportTop(messageId);
  }, 420);
};

export const Thread: FC<{ variant: "home" | "chat" }> = ({ variant }) => {
  const isSession = variant === "chat";
  const userMessageCount = useAuiState(
    (s) =>
      s.thread.messages.filter((message) => message.role === "user").length,
  );
  const anchorUserMessageId = useAuiState((s) => {
    const last = s.thread.messages.at(-1);
    if (!last) return null;

    if (last.role === "assistant") {
      const previous = s.thread.messages.at(-2);
      return previous?.role === "user" ? previous.id : null;
    }

    if (last.role === "user") {
      return last.id;
    }

    return null;
  });
  const isThreadRunning = useAuiState((s) => s.thread.isRunning);
  const previousUserMessageCountRef = useRef(userMessageCount);

  useEffect(() => {
    const prevCount = previousUserMessageCountRef.current;
    const hasNewUserMessage = userMessageCount > prevCount;
    previousUserMessageCountRef.current = userMessageCount;

    if (!isSession || !anchorUserMessageId) return;
    if (!hasNewUserMessage && !isThreadRunning) return;

    scheduleAlignUserMessageByIdToTop(anchorUserMessageId);
  }, [anchorUserMessageId, isSession, isThreadRunning, userMessageCount]);

  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root @container flex h-full flex-col bg-[#fdfdfd] dark:bg-[#141414]"
      style={{
        ["--thread-max-width" as string]: "44rem",
      }}
    >
      <ThreadPrimitive.Viewport
        autoScroll
        turnAnchor="top"
        className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth px-4 pt-4"
      >
        <AuiIf key="home" condition={(s) => !isSession && s.thread.isEmpty}>
          <div className="flex grow flex-col items-center justify-center">
            <GrokIcon className="mb-6 h-10 text-[#0d0d0d] dark:text-white" />
            <div className="mt-8 w-full max-w-(--thread-max-width)">
              <Composer />
            </div>
          </div>
        </AuiIf>

        <ThreadPrimitive.Messages
          key="messages"
          components={{
            UserMessage,
            EditComposer,
            AssistantMessage,
          }}
        />

        <AuiIf key="footer" condition={(s) => isSession || !s.thread.isEmpty}>
          <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible pb-4 md:pb-6">
            <ThreadScrollToBottom />
            <Composer />
          </ThreadPrimitive.ViewportFooter>
        </AuiIf>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:bg-[#212121] dark:hover:bg-[#2a2a2a]"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const Composer: FC = () => {
  const isEmpty = useAuiState((s) => s.composer.isEmpty);
  const isRunning = useAuiState((s) => s.thread.isRunning);

  return (
    <ComposerPrimitive.Root
      className="aui-composer-root group/composer mx-auto w-full max-w-(--thread-max-width)"
      data-empty={isEmpty}
      data-running={isRunning}
    >
      <div className="overflow-hidden rounded-4xl bg-[#f8f8f8] shadow-xs ring-1 ring-[#e5e5e5] ring-inset transition-shadow focus-within:ring-[#d0d0d0] dark:bg-[#212121] dark:ring-[#2a2a2a] dark:focus-within:ring-[#3a3a3a]">
        <ComposerAttachments />

        <div className="flex items-end gap-1 p-2">
          <ComposerPrimitive.AddAttachment className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#0d0d0d] transition-colors hover:bg-[#f0f0f0] dark:text-white dark:hover:bg-[#2a2a2a]">
            <Paperclip width={18} height={18} />
          </ComposerPrimitive.AddAttachment>

          <ComposerPrimitive.Input
            placeholder="Send a message..."
            className="aui-composer-input my-2 h-6 max-h-100 min-w-0 flex-1 resize-none bg-transparent px-2 text-[#0d0d0d] text-base leading-6 outline-none placeholder:text-[#9a9a9a] dark:text-white dark:placeholder:text-[#6b6b6b]"
            autoFocus
            aria-label="Message input"
          />

          <button
            type="button"
            className="mb-0.5 flex h-9 shrink-0 items-center gap-2 rounded-full px-2.5 text-[#0d0d0d] hover:bg-[#f0f0f0] dark:text-white dark:hover:bg-[#2a2a2a]"
          >
            <Moon width={18} height={18} className="shrink-0" />
            <div className="flex items-center gap-1 overflow-hidden transition-[max-width,opacity] duration-300 group-data-[empty=false]/composer:max-w-0 group-data-[empty=true]/composer:max-w-24 group-data-[empty=false]/composer:opacity-0 group-data-[empty=true]/composer:opacity-100">
              <span className="whitespace-nowrap font-semibold text-sm">
                AI Librarian
              </span>
              <ChevronDownIcon width={16} height={16} className="shrink-0" />
            </div>
          </button>

          <div className="relative mb-0.5 h-9 w-9 shrink-0 rounded-full bg-[#0d0d0d] text-white dark:bg-white dark:text-[#0d0d0d]">
            <button
              type="button"
              className="absolute inset-0 flex items-center justify-center transition-all duration-300 ease-out group-data-[empty=false]/composer:scale-0 group-data-[running=true]/composer:scale-0 group-data-[empty=false]/composer:opacity-0 group-data-[running=true]/composer:opacity-0"
              aria-label="Voice mode"
            >
              <Mic width={18} height={18} />
            </button>

            <ComposerPrimitive.Send className="absolute inset-0 flex items-center justify-center transition-all duration-300 ease-out group-data-[empty=true]/composer:scale-0 group-data-[running=true]/composer:scale-0 group-data-[empty=true]/composer:opacity-0 group-data-[running=true]/composer:opacity-0">
              <ArrowUpIcon width={18} height={18} />
            </ComposerPrimitive.Send>

            <ComposerPrimitive.Cancel className="absolute inset-0 flex items-center justify-center transition-all duration-300 ease-out group-data-[running=false]/composer:scale-0 group-data-[running=false]/composer:opacity-0">
              <Square width={14} height={14} fill="currentColor" />
            </ComposerPrimitive.Cancel>
          </div>
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const ChainOfThought: FC = () => {
  const [collapsed, setCollapsed] = useState(true);

  return (
    <ChainOfThoughtPrimitive.Root className="my-2 rounded-lg border border-[#e5e5e5] dark:border-[#2a2a2a]">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full cursor-pointer items-center gap-2 px-4 py-2 text-sm font-medium text-[#6b6b6b] transition-colors hover:bg-[#f0f0f0]/50 dark:text-[#9a9a9a] dark:hover:bg-[#212121]/50"
      >
        {collapsed ? (
          <ChevronRightIcon className="size-4 shrink-0" />
        ) : (
          <ChevronDownIcon className="size-4 shrink-0" />
        )}
        <BrainIcon className="size-4 shrink-0" />
        Thinking
      </button>
      {!collapsed && (
        <ChainOfThoughtPrimitive.Parts
          components={{
            Reasoning: ThinkingText,
            tools: { Fallback: ToolFallback },
          }}
        />
      )}
    </ChainOfThoughtPrimitive.Root>
  );
};

const ThinkingText: FC<{ text: string }> = ({ text }) => {
  return (
    <div className="border-t border-[#e5e5e5] px-4 py-3 text-sm text-[#6b6b6b] dark:border-[#2a2a2a] dark:text-[#9a9a9a]">
      <p className="whitespace-pre-wrap italic">{text}</p>
    </div>
  );
};

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="group/message aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
      data-role="assistant"
    >
      <div className="aui-assistant-message-content wrap-break-word px-2 text-[#0d0d0d] leading-relaxed dark:text-[#e5e5e5]">
        <MessagePrimitive.Parts
          components={{
            Text: MarkdownText,
            ChainOfThought: ChainOfThought,
          }}
        />
        <MessageError />
      </div>

      <div className="aui-assistant-message-footer mt-1 ml-2 flex h-8 items-center">
        <BranchPicker />
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="aui-assistant-action-bar-root -ml-2 flex items-center gap-0.5 text-[#6b6b6b] dark:text-[#9a9a9a]"
    >
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton
          tooltip="Refresh"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <ReloadIcon width={16} height={16} />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton
          tooltip="Copy"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <AuiIf condition={(s) => s.message.isCopied}>
            <CheckIcon className="size-4" />
          </AuiIf>
          <AuiIf condition={(s) => !s.message.isCopied}>
            <CopyIcon width={16} height={16} />
          </AuiIf>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.FeedbackPositive asChild>
        <TooltipIconButton
          tooltip="Helpful"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <ThumbsUp width={16} height={16} />
        </TooltipIconButton>
      </ActionBarPrimitive.FeedbackPositive>
      <ActionBarPrimitive.FeedbackNegative asChild>
        <TooltipIconButton
          tooltip="Not helpful"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <ThumbsDown width={16} height={16} />
        </TooltipIconButton>
      </ActionBarPrimitive.FeedbackNegative>
    </ActionBarPrimitive.Root>
  );
};

const UserMessage: FC = () => {
  const messageId = useAuiState((s) => s.message.id);

  return (
    <MessagePrimitive.Root
      className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto flex w-full max-w-(--thread-max-width) animate-in flex-col items-end gap-y-2 px-2 p-3 duration-150"
      data-role="user"
      data-message-id={messageId}
    >
      <UserMessageAttachments />

      <div className="group/message aui-user-message-content-wrapper relative max-w-[90%] min-w-0 pb-9">
        <div className="aui-user-message-content wrap-break-word rounded-3xl rounded-br-lg border border-[#e5e5e5] bg-[#f0f0f0] px-4 py-3 text-[#0d0d0d] dark:border-[#2a2a2a] dark:bg-[#1a1a1a] dark:text-white">
          <MessagePrimitive.Parts />
        </div>
        <div className="aui-user-action-bar-wrapper absolute right-0 bottom-0 flex h-8 items-center justify-end opacity-0 transition-opacity group-focus-within/message:opacity-100 group-hover/message:opacity-100">
          <UserActionBar />
        </div>
      </div>

      <BranchPicker className="aui-user-branch-picker -mr-1 justify-end" />
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-user-action-bar-root flex items-center gap-0.5"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton
          tooltip="Edit"
          className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6b6b] transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:text-[#9a9a9a] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <Pencil1Icon width={16} height={16} />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton
          tooltip="Copy"
          className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6b6b] transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:text-[#9a9a9a] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
        >
          <CopyIcon width={16} height={16} />
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
      <ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-[#f0f0f0] dark:bg-[#1a1a1a]">
        <ComposerPrimitive.Input
          className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-[#0d0d0d] text-sm outline-none dark:text-white"
          autoFocus
        />
        <div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
          <ComposerPrimitive.Cancel asChild>
            <Button variant="ghost" size="sm">
              Cancel
            </Button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <Button size="sm">Update</Button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </MessagePrimitive.Root>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn(
        "aui-branch-picker-root mr-2 -ml-2 inline-flex items-center text-[#9a9a9a] text-xs",
        className,
      )}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="aui-branch-picker-state font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};
