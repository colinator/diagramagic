# diagramagic patterns

## 1) Full-page column layout
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="680" direction="column" gap="14">
    <diag:flex width="680" padding="12" background-class="card"><text style="font-size:18px">System Overview</text></diag:flex>
    <diag:flex width="680" padding="12" gap="8" background-class="card" direction="column">
      <text style="font-size:14px" diag:wrap="true">This section is laid out with no manual y coordinates.</text>
    </diag:flex>
  </diag:flex>
</diag:diagram>
```

## 2) Card grid via templates
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:template name="card"><diag:flex width="180" padding="10" gap="6" direction="column" background-class="card"><text><diag:slot name="title"/></text><text diag:wrap="true"><diag:slot name="body"/></text></diag:flex></diag:template>
  <diag:flex direction="row" gap="12">
    <diag:instance template="card"><diag:param name="title">A</diag:param><diag:param name="body">First card body text.</diag:param></diag:instance>
    <diag:instance template="card"><diag:param name="title">B</diag:param><diag:param name="body">Second card body text.</diag:param></diag:instance>
  </diag:flex>
</diag:diagram>
```

## 3) Nested flex sections
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="700" direction="column" gap="12">
    <diag:flex direction="row" gap="12">
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>Backlog</text><text diag:wrap="true">Gather requirements.</text></diag:flex>
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>In Progress</text><text diag:wrap="true">Implement renderer.</text></diag:flex>
      <diag:flex width="220" padding="10" direction="column" gap="6" background-class="lane"><text>Done</text><text diag:wrap="true">Publish package.</text></diag:flex>
    </diag:flex>
  </diag:flex>
</diag:diagram>
```

## 4) Embedded sub-diagram with <g transform>
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="420" padding="12" gap="8" direction="column" background-class="panel">
    <text>Service Detail</text>
    <g transform="scale(0.45)">
      <diag:flex width="760" padding="12" gap="8" direction="column" background-class="card">
        <text style="font-size:18px">Internal Flow</text>
        <text diag:wrap="true">This nested sub-diagram contributes to parent layout bounds.</text>
      </diag:flex>
    </g>
  </diag:flex>
</diag:diagram>
```

## 5) Mixed raw SVG + flex
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#555"/></marker></defs>
  <diag:flex id="left" x="20" y="30" width="180" padding="10" background-class="card"><text>API</text></diag:flex>
  <diag:flex id="right" x="300" y="30" width="180" padding="10" background-class="card"><text>DB</text></diag:flex>
  <line x1="200" y1="50" x2="300" y2="50" stroke="#555" marker-end="url(#arrow)"/>
</diag:diagram>
```

## 6) diag:arrow between id targets
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex id="auth" x="20" y="40" width="180" padding="10" background-class="card">
    <text style="font-size:14px">Auth</text>
  </diag:flex>
  <diag:flex id="db" x="320" y="40" width="180" padding="10" background-class="card">
    <text style="font-size:14px">Database</text>
  </diag:flex>
  <diag:arrow from="auth" to="db" label="queries" stroke="#e67e22" stroke-width="1.5"/>
</diag:diagram>
```

## 7) Sequence-style anchors + arrows
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex id="client_lane" x="20" y="20" width="180" padding="10" background-class="card">
    <text>Client</text>
  </diag:flex>
  <diag:flex id="server_lane" x="320" y="20" width="180" padding="10" background-class="card">
    <text>Server</text>
  </diag:flex>
  <diag:anchor id="c_t1" relative-to="client_lane" side="bottom" offset-y="40"/>
  <diag:anchor id="s_t1" relative-to="server_lane" side="bottom" offset-y="40"/>
  <diag:arrow from="c_t1" to="s_t1" label="SYN"/>
</diag:diagram>
```

## 8) Include a sub-diagram file
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="620" direction="column" gap="12">
    <diag:flex width="620" padding="10" background-class="card">
      <text style="font-size:16px">System Summary</text>
    </diag:flex>
    <diag:include src="details/auth_flow.svg++" x="0" y="0" scale="0.9"/>
  </diag:flex>
</diag:diagram>
```

## 9) Flowchart with diag:graph
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <style>
    .box { fill:#e8f4f8; stroke:#2980b9; stroke-width:1; rx:4; }
  </style>
  <diag:graph direction="TB" node-gap="28" rank-gap="44">
    <diag:node id="start" padding="10" background-class="box"><text style="font-size:13px">Start</text></diag:node>
    <diag:node id="process" padding="10" background-class="box"><text style="font-size:13px">Process Data</text></diag:node>
    <diag:node id="done" padding="10" background-class="box"><text style="font-size:13px">Done</text></diag:node>
    <diag:edge from="start" to="process" label="step"/>
    <diag:edge from="process" to="done"/>
  </diag:graph>
</diag:diagram>
```

## 10) Service dependency graph (LR)
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <style>
    .svc { fill:#ffeaa7; stroke:#fdcb6e; stroke-width:1; rx:6; }
    .db { fill:#dfe6e9; stroke:#636e72; stroke-width:1; rx:6; }
  </style>
  <diag:graph direction="LR" node-gap="20" rank-gap="52">
    <diag:node id="client" padding="10" background-class="svc"><text style="font-size:12px">Client</text></diag:node>
    <diag:node id="api" padding="10" background-class="svc"><text style="font-size:12px">API</text></diag:node>
    <diag:node id="auth" padding="10" background-class="svc"><text style="font-size:12px">Auth</text></diag:node>
    <diag:node id="db" padding="10" background-class="db"><text style="font-size:12px">Database</text></diag:node>
    <diag:edge from="client" to="api" label="HTTPS"/>
    <diag:edge from="api" to="auth" label="verify"/>
    <diag:edge from="api" to="db" label="query"/>
    <diag:edge from="auth" to="db" stroke-dasharray="4 2"/>
  </diag:graph>
</diag:diagram>
```

## 11) Hybrid graph + sections (recommended for dense architecture diagrams)
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="980" direction="column" gap="12">
    <diag:flex width="980" padding="10" background-class="header"><text style="font-size:22px;font-weight:bold">Service Topology</text></diag:flex>
    <diag:flex width="980" direction="row" gap="12">
      <diag:flex width="720" padding="10" background-class="panel">
        <diag:graph direction="LR" node-gap="18" rank-gap="44">
          <diag:node id="gw" width="180" padding="8" background-class="svc"><text style="font-size:13px;font-weight:bold">API Gateway</text><text style="font-size:11px" diag:wrap="true">authn, rate limit, routing</text></diag:node>
          <diag:node id="auth" width="180" padding="8" background-class="svc"><text style="font-size:13px;font-weight:bold">Auth</text><text style="font-size:11px" diag:wrap="true">JWT + session checks</text></diag:node>
          <diag:node id="db" width="180" padding="8" background-class="db"><text style="font-size:13px;font-weight:bold">DB</text><text style="font-size:11px" diag:wrap="true">primary + read replica</text></diag:node>
          <diag:edge from="gw" to="auth" label="verify"/>
          <diag:edge from="auth" to="db" label="lookup"/>
        </diag:graph>
      </diag:flex>
      <diag:flex width="248" padding="10" gap="8" direction="column" background-class="legend">
        <text style="font-size:14px;font-weight:bold">Legend</text>
        <text style="font-size:12px" diag:wrap="true">Use graph for topology, but keep context and annotations outside graph nodes when dense.</text>
      </diag:flex>
    </diag:flex>
  </diag:flex>
</diag:diagram>
```

## 12) Sequence diagram pattern (prefer anchors/arrows over graph)
```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns" diag:padding="20">
  <diag:flex width="920" direction="column" gap="10">
    <diag:flex width="920" direction="row" gap="20">
      <diag:flex id="lane_client" width="260" padding="8" background-class="lane"><text style="font-size:14px">Client</text></diag:flex>
      <diag:flex id="lane_api" width="260" padding="8" background-class="lane"><text style="font-size:14px">API</text></diag:flex>
      <diag:flex id="lane_db" width="260" padding="8" background-class="lane"><text style="font-size:14px">DB</text></diag:flex>
    </diag:flex>
    <diag:anchor id="c1" relative-to="lane_client" side="bottom" offset-y="40"/>
    <diag:anchor id="a1" relative-to="lane_api" side="bottom" offset-y="40"/>
    <diag:anchor id="d1" relative-to="lane_db" side="bottom" offset-y="80"/>
    <diag:arrow from="c1" to="a1" label="POST /login"/>
    <diag:arrow from="a1" to="d1" label="SELECT user"/>
    <diag:arrow from="d1" to="a1" label="row data"/>
  </diag:flex>
</diag:diagram>
```
