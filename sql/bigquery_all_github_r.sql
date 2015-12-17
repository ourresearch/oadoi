select
  repository_url
from [githubarchive:github.timeline]
where
    type="PushEvent"
    and repository_language="R"
group by
  repository_url
order by
repository_url