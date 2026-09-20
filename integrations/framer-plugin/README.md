# Framer project bridge: experimental adapter

`export.ts` is a read-only adapter for use inside an official Framer plugin scaffold. It is not a published plugin, not a complete standalone Framer plugin package, and has not been run inside the Framer editor. The separate Frameport JSON importer is implemented.

Create the official scaffold using `npm create framer-plugin@latest`, copy `export.ts` into its source, import `framer` from `framer-plugin`, and call `createManifest(framer, publishedUrl, includeCMS)` from your UI. Check the current SDK types against the adapter interface before building. The scaffold supplies plugin identifiers, modes, bundling and platform configuration; this repository does not invent those values or fake a dependency lock.

Offer a URL field, an explicit optional CMS checkbox and an Export button. Import `downloadManifest` to save the resulting JSON. Import that file through Frameport's **Project manifest** tab. The published website is still required. No API keys are sent to another host.

The adapter reads the current canvas root, bounded child metadata and optional readable collections. It does not read private user/account information, mutate the project, publish it, export proprietary runtime modules, promise all canvases, or compile the original canvas tree. CMS JSON is archived as reference content, not automatically wired into the exported pages. Review draft CMS records and asset rights before sharing exports.

Official references checked on 20 September 2026:
- https://www.framer.com/developers/reference
- https://www.framer.com/developers/cms
- https://www.framer.com/developers/plugins-quick-start
