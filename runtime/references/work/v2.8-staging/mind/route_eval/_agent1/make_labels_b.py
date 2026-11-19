# -*- coding: utf-8 -*-
# Independent second rater (agent 1). Labels written by hand from reading
# playbooks_for_labeling_v28.json and fresh_cc.json only.
import json, sys, collections

BASE = r"C:\Users\cinde\rd-staging\v2.8\mind\route_eval"
OUT = BASE + r"\labels_fresh_b.json"

# fid|best|ok (comma separated)|why
RAW = """
0|skip||pasted chat-library update with no actual request
1|app-dev||update the desktop dragon app
2|app-dev||update the desktop app on Desktop
3|app-dev|pc-task|open the freshly updated app build
4|download|self-improve,pc-task|download all montage tools and skills into folder
5|download|pc-task,self-improve|follow-up: install the downloaded montage tools
6|download|re-repo,self-improve|download necessary GitHub repos
7|re-repo|self-improve,download,deep-research|find montage repos, download and wire them in
8|self-improve|re-repo,re-file,download|install REA and apps to extend own abilities
9|re-repo|self-improve,deep-research,download|search top 500 GitHub repos and install useful ones
10|self-improve|docs-office,build-skill|write instructions file listing tools and skills
11|re-repo|self-improve,download|analyse top 500 GitHub video repos and install
12|self-improve|download,pc-task|download apps, skills, tools that help Claude
13|reel-montage|design-static,lyric-quran|bare title in montage folder; likely tribute video
14|self-improve||activate Black Dragon and superpowers in folder instructions
15|self-improve|reel-montage|"start" continues previous activation task
16|reel-montage|lyric-quran,voice,download|song in montage output does not play
17|status||where is the skill, are you done
18|status||are you done
19|self-improve|build-skill,status,ship|finish the dragon skill and report folder
20|status||how much left, what are you doing
21|self-improve|build-skill,none|agent-count tweak on ongoing dragon skill work
22|status||done or not yet
23|status||where is the skill
24|self-improve|re-repo,build-skill|merge GitHub montage skills into Black Dragon
25|skip||pasted shell commands only
26|skip||pasted shell and curl commands only
27|app-dev|clone-own-tool|make Black Dragon a Windows app using API
28|app-dev||the app is stuck, fix it
29|app-dev||add attachments, folder picker, balance to app
30|app-dev||show agent running state and output preview
31|app-dev||running indicator and multiple chats feature
32|app-dev||enable auto-approve permissions in app
33|app-dev|self-improve|develop the app and its capabilities
34|status|app-dev|cannot find where the program is
35|app-dev||let app run on Claude subscription
36|app-dev||add switch between billed API and subscription
37|app-dev||make agent count setting open
38|app-dev||decoded: app should work with other AI subscriptions
39|app-dev||update, develop and open the app
40|app-dev||ChatGPT provider in app not working
41|app-dev||show created files panel on the left
42|app-dev||drag and drop broken in app
43|app-dev||add Chrome and PC control plus extension
44|app-dev|status|why did the app not update
45|app-dev||enable Antigravity usage inside app
46|app-dev||add optional blind analysis mode to app
47|app-dev||add merging multiple chats feature
48|app-dev||update the app
49|app-dev||make app use Antigravity when open
50|app-dev||model list missing Fable 5.2, update
51|app-dev||add window size control to app
52|app-dev||add zero-memory session option
53|app-dev||update button broken, fix
54|app-dev||update whole app, explain actions, fix bugs
55|status|app-dev|does the app now have all abilities
56|toon|status,app-dev|asks whether Disney-style conversion models are linked
57|app-dev|toon|do both options and wire into app
58|re-repo|status,none|capability question about GitHub connection
59|re-repo|build-skill,self-improve|analyse REA GitHub repo and build super skill
60|re-repo|self-improve,deep-research|analyse any needed apps, sites, repos
61|re-repo|self-improve,build-skill|"continue" the repo analysis work
62|build-skill|draw-math|wants new math/physics skill for montage
63|build-skill|clone-own-tool,self-improve|mid-task addition: focus cloud browser and downloader
64|self-improve|ship,build-skill|update attached Black Dragon zip with capabilities
65|status||did you add reverse engineering tools
66|app-dev||wants checkboxes to select analysis tools in app
67|app-dev|ship|update version and put on Desktop
68|app-dev||fix any problems in the app build
69|app-dev||the app does not work
70|app-dev||add voice input, verify RE tools selectable
71|ship|status|send the file zipped
72|ship||upload it and give link
73|reconcile|excel-pro|"yes prepare it" after account statement file
74|chrome-task|pc-task|wants it inside browser tabs
75|pc-task|chrome-task,deep-research|explain how to do it in Firefox
76|chrome-task|pc-task|how to rename a browser tab
77|chrome-task|pc-task|how to auto-restore tabs on launch
78|chrome-task|pc-task|unclear follow-up about browser tabs behaviour
79|none||acknowledgement only
80|motion-code||make impactful motion graphics animation
81|status||done?
82|motion-code|status|output file does not work, fix previous job
83|none||language instruction only
84|think-hard|docs-office,app-dev,none|write the change clearly as agent instructions; context unknown
85|reconcile||do a reconciliation, what is the difference
86|reconcile||where is the ~200 difference
87|excel-pro|docs-office,reconcile|restyle sheet with nicer colours and fonts
88|excel-pro|reconcile,docs-office,status|row number 2 missing in sequence
89|excel-pro|reconcile,docs-office|redo the numbering sequence
90|reconcile||is this beneficiary present in statements
91|reconcile||did beneficiary receive money or all returned
92|reconcile||same analysis for transfers to another party
93|reconcile||when was the loan in the statements
94|reconcile|think-hard|professional review; followed by matching statements
95|reconcile||yes, match them
96|reconcile||yes, match it
97|none|chrome-task|login done notice, no task stated
98|none|status|memory probe test prompt
99|none||test: say one word
100|none||test: say one word
101|paid-gen|cloud-render,none|call Higgsfield balance tool
102|pc-task|motion-code,none|run one ffmpeg command in PowerShell
103|status||what file name did you create
104|build-skill|blender-3d,self-improve,clone-own-tool|build Blender, downloader, stealth browser skills
105|re-repo|none,build-skill,self-improve|approval continuing the 20-agent REA repo job
106|deep-research|download|find 500 sites with HQ footage and images
107|cloud-render|none,web-build|fragment "cloud server"; closest is cloud offload
108|web-build|re-site,site-style,deep-research|build car parts catalogue site like reference
109|web-build|re-site|analyse artifact, build 3D car parts database site
110|reel-montage|download,lyric-quran,trend|montage for song with downloaded Riyadh footage
111|reconcile||match two account statement files
112|reconcile|none|"no, enough" inside reconciliation session
113|reconcile|excel-pro|extract international transfers from bank statements
114|reconcile||which statements do you need
115|reconcile||bank account files mapped to companies
116|reconcile||supplier invoices and statements to use
117|reconcile|excel-pro|sheets of transfers, returns, net, invoices
118|reconcile|none|"not needed" reply inside reconciliation
119|reconcile|excel-pro|improve formatting of reconciliation workbook
120|reconcile||table of inter-company transfers before supplier payment
121|reconcile|excel-pro|"update" the reconciliation output
122|reconcile||returned transfers re-sent with same amount
123|reconcile||table tracing transfer, return, re-transfer
124|reconcile||clarify in a table, same transfers work
125|reconcile||trace how returned transfers were re-sent
126|reconcile||"yes add it" to reconciliation workbook
127|reconcile||direct and intermediary transfers to supplier
128|reconcile||confirmation inside reconciliation
129|reconcile|excel-pro,status|save reconciliation file under a name
130|reconcile||transfer dates for a beneficiary
131|toon||asks for video-to-Disney model
132|skip||only app control boilerplate, no request
133|cloud-render|deep-research|free Higgsfield resources for rendering
134|status||where are the skills you made
135|clone-own-tool|re-file,app-to-skill|look at folder; existing app for virtual camera project
136|clone-own-tool||virtual camera to Android live video issue
137|clone-own-tool||phone should see virtual camera as real
138|clone-own-tool||put program in Android emulator with TikTok
139|clone-own-tool||build lightweight emulator inside own app
140|clone-own-tool|download|download whatever is needed for emulator
141|status||done?
142|clone-own-tool||emulator must see the virtual camera
143|clone-own-tool||connect camera to emulator, programming bug
144|clone-own-tool||fix the problem in emulator camera project
145|ship|clone-own-tool|send the complete app
146|clone-own-tool|pc-task|install it on PC and run
147|clone-own-tool|pc-task|try running the built tool
148|clone-own-tool||why emulator did not open
149|clone-own-tool||emulator very slow
150|clone-own-tool||improve whole emulator, verify TikTok works
151|clone-own-tool||same problem, try different emulator
152|clone-own-tool||fix linking virtual camera problem
153|app-dev|self-improve|develop open dragon app with all abilities
154|app-dev||add full computer control to app
155|app-dev|build-skill,app-to-skill|app feature: turn added file into saved skill
156|self-improve|build-skill,ship|upgrade Black Dragon package zip with all capabilities
157|status||did you develop it, where is it
158|pc-task|ship,status|make Desktop folder and put file in
159|pc-task|ship|save file to Desktop with a name
160|build-skill|app-dev,cloud-render|skill exploiting free Higgsfield capabilities for app
161|app-dev|cloud-render,paid-gen|connect Higgsfield MCP to the app
162|app-dev|self-improve,image-identity,nature-palette|complaint: app misunderstood bird palette identity request
163|build-skill|app-dev|add it as a new skill in app
164|ship||zip with all Black Dragon capabilities on Desktop
165|pc-task|self-improve,status|"open it" after skill build
166|status||did you make the White Dragon
167|app-dev|build-skill,audit-install|install it as skill in desktop app
168|self-improve|app-dev,app-to-skill,build-skill,re-file|analyse folder, form Red Dragon, upgrade everything
169|app-dev|self-improve|develop app, add top 200 Claude skills
170|app-dev|pc-task|reopen app after update
171|pc-task|app-dev|open the Red Dragon app
172|app-dev|self-improve|develop this app and rename Red Dragon
173|status||did you add the 200 skills
174|app-dev||update broken; fix update mechanism
175|app-dev|status|how to enable 200 skills in app
176|app-dev||only 43 skills show in app
177|ship|app-dev|apply update and zip all app files
178|app-dev||multi-select skills feature
179|app-dev||select all skills at once feature
180|app-dev||bug in selection and list UI
181|app-dev|self-improve,re-repo|add 500 repos and 500 skills to app
182|app-dev||app should show its thinking
183|app-dev|self-improve|update dragon build, fix incomplete update
184|app-dev||fix the update problem
185|app-dev||"fix it" continues update bug
186|app-dev|self-improve|improve updater cmd script for dragon
187|re-file|none|use REA binary_session and explain its tools
188|skip||bare path with no request
189|clone-own-tool||invent own app with recording, download, screen control
190|clone-own-tool||"all" answers options for own app
191|clone-own-tool|status|how to run the built app
192|clone-own-tool|status|what are login details for the app
193|clone-own-tool||provides login credentials for own player app
194|clone-own-tool||add live recording and multi-view playback
195|clone-own-tool|app-dev|update own player app on Desktop
196|clone-own-tool||save recordings to Desktop folder
197|clone-own-tool||improve search by section and descriptions
198|clone-own-tool|web-build|update desktop build and make web version
199|clone-own-tool||tap player screen to pause or seek
200|web-build|clone-own-tool|website with same features, login from iPhone
201|status||where is the link
202|pc-task|status,web-build|put link in text file on Desktop
203|web-build|clone-own-tool,ship|site down; host it on cloud server
204|clone-own-tool|web-build,re-site|add content fetching from other sites
205|clone-own-tool|web-build|extract and play video from page without ads
206|clone-own-tool|download|download feature in own app not working
207|self-improve|build-skill,app-to-skill,re-repo|use REA to develop and reorganise superpower skills
208|re-site|site-style,web-build|analyse artifact and Apple site, suggest improvements
209|re-site|ship,pc-task,status|put analysis result in Desktop folder
210|site-style|web-build,re-site,think-hard|suggest colours, fonts, details for artifact
211|web-build|chrome-task,ship|can you publish and edit site directly
212|site-style|web-build|start; apply Apple colours and harmony
213|site-style|re-site,web-build|use REA in the ongoing site restyle
214|site-style|web-build,ship,pc-task|put the full file on Desktop
215|site-style|re-site|extract Apple fonts, theme, transitions for own site
216|site-style|pc-task,docs-office|save style analysis to Desktop file
217|app-to-skill||analyse folder with REA into Claude skill with protocol
218|app-to-skill||analyse app with REA and convert to skill
219|app-to-skill|build-skill|"add all" continues app-to-skill job
220|app-to-skill|build-skill|complete the skill
221|pc-task|app-dev,none|reconnect to new Claude account
222|re-repo|status,self-improve|can you see the superpower and dragon repos
223|self-improve|build-skill|merge all skills into one super dragon skill
224|self-improve|build-skill,pc-task,audit-install|install the merged super skill
225|self-improve|build-skill|continue developing the super skill
"""

pbs = [p["id"] for p in json.load(open(BASE + r"\playbooks_for_labeling_v28.json", encoding="utf-8"))]
msgs = json.load(open(BASE + r"\fresh_cc.json", encoding="utf-8"))
valid = set(pbs)
out, errs = [], []
for line in RAW.strip().splitlines():
    fid, best, ok, why = line.split("|", 3)
    fid = int(fid)
    oks = [o for o in ok.split(",") if o]
    if best not in valid and best not in ("none", "skip"):
        errs.append("bad best %d %s" % (fid, best))
    for o in oks:
        if o not in valid and o != "none":
            errs.append("bad ok %d %s" % (fid, o))
    if best in oks:
        errs.append("best in ok %d" % fid)
    if len(why.split()) > 12:
        errs.append("why too long %d (%d words)" % (fid, len(why.split())))
    out.append({"fid": fid, "best": best, "ok": oks, "why": why})

if [o["fid"] for o in out] != [m["fid"] for m in msgs]:
    errs.append("fid order/count mismatch: %d vs %d" % (len(out), len(msgs)))

sys.stdout.reconfigure(encoding="utf-8")
if errs:
    print("ERRORS:"); print("\n".join(errs)); sys.exit(1)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

chk = json.load(open(OUT, encoding="utf-8"))
print("playbooks:", len(pbs), "| items:", len(chk), "| json ok")
c = collections.Counter(o["best"] for o in chk)
print(" ".join("%s=%d" % kv for kv in c.most_common()))
print("unused playbooks:", [p for p in pbs if p not in c])
