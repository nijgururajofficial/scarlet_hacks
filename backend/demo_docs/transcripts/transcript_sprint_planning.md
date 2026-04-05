# Meeting Transcript — Sprint 23 Planning
**Date:** January 13, 2025
**Duration:** 52 minutes
**Attendees:** Priya Nair (EM), David Kim (Tech Lead), Sarah Chen (Platform), Aaliya Torres (Senior Eng), James Okafor (Engineer), Riya Patel (Engineer, new joiner - week 3)
**Recorded by:** Otter.ai (auto-transcript — may contain errors)

---

**Priya Nair** 00:00:12
Okay I think we're all here now. Marcus said he's gonna be 5 minutes late, he's dealing with something in staging. Let's get started and he can catch up. So today is sprint 23 planning, we have 18 tickets to go through, I'm gonna try and keep us under an hour. Riya, welcome to your first sprint planning by the way.

**Riya Patel** 00:00:31
Thanks, yeah excited. Little nervous haha

**Priya Nair** 00:00:35
Don't be, it's chaotic for everyone. Okay so first thing — David do you want to walk us through the carryover from sprint 22?

**David Kim** 00:00:43
Yeah so we had 4 tickets carry over. ACM-389 the soft delete bug, that one's done actually, Aaliya merged it this morning. ACM-371 the pagination refactor, that's still in review — James can you get eyes on that today? It's been sitting 3 days.

**James Okafor** 00:01:02
Oh yeah sorry, I thought someone else had picked that up. I'll do it after this call.

**David Kim** 00:01:07
Cool. ACM-355 the webhook retry logic, that one's blocked on a decision we need to make today actually so let's come back to it. And ACM-340 the Stripe integration bug, Sarah?

**Sarah Chen** 00:01:19
Yeah so that one's... okay so it's complicated. The bug itself is fixed but when I was testing I found another issue in the billing sync, it's not related to the original ticket but it's kind of bad. Like if a subscription gets cancelled and then reactivated within the same billing period we're creating a duplicate invoice record.

**Priya Nair** 00:01:38
How bad is bad?

**Sarah Chen** 00:01:41
I mean it doesn't charge the customer twice, Stripe handles the actual charging. But our internal records are wrong, so the dashboard shows incorrect billing history. We've had 2 support tickets about it this week already.

**Priya Nair** 00:01:54
Okay that needs to go in this sprint then. Can you scope it?

**Sarah Chen** 00:01:58
Yeah probably a day and a half. I need to write a migration to fix the existing bad records too, not just the going-forward fix.

**David Kim** 00:02:06
And the migration needs to run before the code deploy or after?

**Sarah Chen** 00:02:10
Before. Definitely before. If we deploy the code first it'll make the data worse.

**David Kim** 00:02:14
Okay let's make a note of that, this is the kind of thing that bites us at 11pm on a deploy night.

**Priya Nair** 00:02:20
I'll add it to the deploy checklist. Okay James, ACM-355, webhook retry — what's the decision we need to make?

**James Okafor** 00:02:28
So right now when a webhook delivery fails we retry 3 times with no backoff. Just immediate retry, immediate retry, immediate retry. Which is kind of dumb because if the receiving server is down, hammering it 3 times in 2 seconds isn't gonna help. I want to add exponential backoff. But the question is what do we do with the DLQ items that are already in there? There's like 340 of them from last week when that customer's endpoint was down.

**Aaliya Torres** 00:02:54
We should just replay them. If their server is back up now they'd probably want the events.

**James Okafor** 00:02:59
Yeah but some of those are 6 days old. Like a `user.created` event from 6 days ago, is that useful to send now?

**David Kim** 00:03:07
That's a good point actually. I think we need to differentiate by event type. Time-sensitive events like... what would be time sensitive...

**Sarah Chen** 00:03:16
Billing events are time sensitive. If `billing.invoice.paid` fires 6 days late that could cause real issues on the customer's side.

**David Kim** 00:03:22
Right. But `project.created` probably doesn't matter much if it's late.

**Aaliya Torres** 00:03:27
So are we saying we add a TTL to webhook events? Like each event type has a max age after which we drop it instead of retrying?

**James Okafor** 00:03:35
That would work. Default TTL of like 24 hours, billing events get 72 hours?

**Priya Nair** 00:03:41
I like that. David is that reasonable to scope?

**David Kim** 00:03:44
It's more than I thought this ticket was going to be honestly. The backoff itself is like 2 hours. Adding TTLs and the DLQ replay logic and making it configurable per event type... that's more like 2 days.

**James Okafor** 00:03:56
Could we ship the backoff now and the TTL stuff as a follow-up ticket?

**David Kim** 00:04:01
Yeah I think that's smarter. Ship the backoff, that fixes the immediate problem. File a new ticket for the TTL/replay logic. Priya?

**Priya Nair** 00:04:08
Agreed. James file the follow-up ticket before end of day. Okay let's move on, we've got 16 more tickets to get through and—

**[Marcus Webb joins]**

**Marcus Webb** 00:04:17
Sorry sorry. Staging was throwing 502s, turned out to be a memory leak in the new search service. I've rolled it back for now.

**Priya Nair** 00:04:26
Memory leak? In the OpenSearch wrapper?

**Marcus Webb** 00:04:30
No the actual service code. Riya I think this might be your change actually, the one from last week? The async search handler?

**Riya Patel** 00:04:39
Oh... oh no. Was it the connection not being closed?

**Marcus Webb** 00:04:43
Yeah exactly. The elasticsearch client connection wasn't being released after the search completed. In local testing it's fine because you're only doing like 5 searches. In staging under load it just accumulates.

**Riya Patel** 00:04:55
I'm so sorry, I should have caught that. I can fix it today.

**Marcus Webb** 00:04:59
Don't stress, it happens to everyone. Genuinely. The fix is like 3 lines, use a context manager for the client. I can show you after this call.

**David Kim** 00:05:08
Can we also add a test for this? Like a test that simulates multiple concurrent searches and checks that connections are being released?

**Marcus Webb** 00:05:15
Yeah good call. Riya you want to own that?

**Riya Patel** 00:05:18
Yes, definitely. I'll write the fix and the test.

**Priya Nair** 00:05:22
Make that ACM-... what are we at, 412?

**David Kim** 00:05:26
413 I think. Let me check. Yeah 413.

**Priya Nair** 00:05:30
ACM-413, assign to Riya, let's keep it in this sprint. Okay, new feature tickets — David can you pull up the Linear board? I want to go through the three features that came in from product last week.

**David Kim** 00:05:42
Yeah one sec... okay so we have ACM-401 bulk user export, ACM-402 project archiving improvements, and ACM-403 API key rotation UI. Product ranked them in that order but I honestly think API key rotation should be higher, we've had 4 customers ask for it.

**Aaliya Torres** 00:05:59
I agree. Bulk export is nice to have. API key rotation is a security thing.

**Priya Nair** 00:06:04
What does product say? Has anyone talked to... is it Kenji who owns this?

**David Kim** 00:06:09
Kenji yeah. I haven't talked to him specifically about the priority. I just know their ranking.

**Priya Nair** 00:06:15
Let's not reorder product's priorities without talking to them first. Can someone message Kenji today and get his take? Like explain the customer ask context?

**Aaliya Torres** 00:06:24
I can do that.

**Priya Nair** 00:06:26
Great. In the meantime let's scope all three. Aaliya, bulk export?

**Aaliya Torres** 00:06:32
So bulk export of users... the actual query is easy. The issue is for large orgs this could be like 50,000 rows. We can't do that synchronously.

**David Kim** 00:06:42
Background job?

**Aaliya Torres** 00:06:44
Yeah it has to be. Queue the export, generate a CSV, upload to S3, send them a download link via email.

**James Okafor** 00:06:51
We already do something similar for billing exports right?

**Sarah Chen** 00:06:54
Yeah I can share that code as a reference. It's like 80% the same pattern.

**Aaliya Torres** 00:06:59
Oh that would save a lot of time. If Sarah shares that I'd say 1.5 days including tests.

**Priya Nair** 00:07:06
Good. Project archiving improvements — what does that even mean, the ticket is vague.

**David Kim** 00:07:12
I talked to Kenji about this one. Right now when you archive a project it just disappears from the main view. Customers want an archived section they can browse and search, and the ability to restore a project. Also bulk archive — like select 10 projects and archive them all at once.

**James Okafor** 00:07:27
The restore part is interesting — do we soft-delete currently or hard-delete on archive?

**Sarah Chen** 00:07:32
Soft delete. The data is still there, it just has an `archived_at` timestamp.

**James Okafor** 00:07:36
Okay then restore is easy, just null out `archived_at`.

**David Kim** 00:07:40
The UI work is probably bigger than the backend here. The archived section with search and bulk select, that's a few days of frontend work.

**Priya Nair** 00:07:48
That's a frontend ticket then, not backend. Let's split it. Backend is like half a day, frontend is 2-3 days and goes to the front end team. Can someone write the split tickets?

**David Kim** 00:07:59
I'll do it.

**Priya Nair** 00:08:02
Okay API key rotation UI, James?

**James Okafor** 00:08:06
So this is the thing where customers want to rotate their API keys without downtime. The pattern is: create new key, old key stays valid for 24 hours, then expires. Backend we already kind of support this, the keys table has a `expires_at` column we've never used.

**David Kim** 00:08:22
Oh I didn't know that was there. Who added that?

**Sarah Chen** 00:08:25
I did, like a year ago, for exactly this reason. Never got prioritised.

**David Kim** 00:08:29
Ha. Good foresight. So the backend is mostly there, it's the UI and the flow?

**James Okafor** 00:08:34
Yeah. And we need to notify the customer when their old key is about to expire during the overlap window. Email plus an in-app banner.

**Aaliya Torres** 00:08:42
The email is easy with the existing notification service. In-app banner is a frontend thing.

**Priya Nair** 00:08:47
Okay I want to check — are we trying to fit all three of these in this sprint? Because we're already at 12 points with the carryover and the billing bug.

**David Kim** 00:08:56
Honestly no. I'd say API key rotation because of the customer asks, and leave bulk export and archiving for next sprint.

**Priya Nair** 00:09:03
Aaliya, you said you'd message Kenji?

**Aaliya Torres** 00:09:06
Yeah I'll message him right after this.

**Priya Nair** 00:09:08
Okay let's plan as if API key rotation is in and the others are out, and if Kenji has strong feelings we'll revisit. Deal?

**[general agreement]**

**Priya Nair** 00:09:17
Okay last thing — we had an incident last Tuesday, the API was slow for about 40 minutes, Marcus you did the post-mortem?

**Marcus Webb** 00:09:25
Yeah so what happened is we had a missing index on the `projects` table, specifically on `owner_id`. A customer ran a query that did a full table scan on 2 million rows and it just killed the DB CPU. The fix was adding the index, which took about 8 minutes to build on the live DB.

**David Kim** 00:09:44
How did we miss that index?

**Marcus Webb** 00:09:47
Honestly? The query worked fine in staging because staging only has like 50,000 rows. It's only at scale that it became a problem. The action item from the post-mortem is we're adding a query analyzer step to CI — it'll flag any new queries that are doing sequential scans.

**David Kim** 00:10:02
Is that technically feasible in CI? Like how do you test query plans without production data volumes?

**Marcus Webb** 00:10:08
You can use EXPLAIN ANALYZE with a seeded dataset that's bigger than what we currently seed. I'm looking at using pgbench to generate like 500k rows in the test DB. It won't catch everything but it'll catch the obvious cases.

**David Kim** 00:10:22
I like it. Make it a ticket?

**Marcus Webb** 00:10:25
Already filed. ACM-411.

**Priya Nair** 00:10:28
Great. Okay I think we've gone through the main stuff. Quick check — anyone blocked on anything? Anyone need anything from me?

**Riya Patel** 00:10:36
I just want to say sorry again about the memory leak thing. I should have thought about connection management more carefully.

**Priya Nair** 00:10:43
Riya, seriously, stop. You're 3 weeks in, you found a real bug and you're fixing it. That's exactly what we want. Marcus has caused worse incidents than this and he's still employed.

**Marcus Webb** 00:10:54
I resent that but it's also completely true.

**[laughter]**

**Priya Nair** 00:10:59
Okay we're done. Notes will be in Notion. Standups tomorrow at 9:30.

---

*[End of transcript — 52 minutes 14 seconds]*

*Auto-generated by Otter.ai. May contain transcription errors. For corrections contact Priya Nair.*
