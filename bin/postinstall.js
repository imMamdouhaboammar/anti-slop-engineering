#!/usr/bin/env node
// A package lifecycle hook must not download skills, prompt, or build native code.
// Setup is explicit so that the user can review the plan and choose installed skills.
console.log('[anti-slop] Package ready. Run "anti-slop-engineering setup" to choose core and optional skills.')
