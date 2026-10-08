import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { remarkCitations } from "@/lib/citations";
import { isPhoneHref, remarkPhoneLinks } from "@/lib/phones";
import type { Source } from "@/lib/api";

// Renders assistant markdown (bold, lists, links, etc.) safely as HTML, with
// linked citations and tap-to-call phone numbers.
export default function Markdown({ children, sources = [] }: { children: string; sources?: Source[] }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkCitations, { sources }], remarkPhoneLinks]}
        // Keep react-markdown's URL sanitising; additionally allow plain dial links.
        urlTransform={(url) => (isPhoneHref(url) ? url : defaultUrlTransform(url))}
        components={{
          // Phone links dial in place; web links open a new tab.
          a: ({ node, ...props }) => /^(tel|sms):/.test(props.href ?? "")
            ? <a {...props} />
            : <a {...props} target="_blank" rel="noreferrer" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
