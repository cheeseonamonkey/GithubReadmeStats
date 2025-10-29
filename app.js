
export default async (req, res) => {
  const { username = 'octocat' } = req.query;

  try {
    // Fetch all repos
    const reposRes = await fetch(
      `https://api.github.com/users/${username}/repos?per_page=100&type=owner`,
      { headers: { 'User-Agent': 'GitHub-Stats' } }
    );

    if (!reposRes.ok) throw new Error('User not found');

    const repos = await reposRes.json();
    const languages = {};

    // Get languages for each repo
    for (const repo of repos) {
      const langRes = await fetch(repo.languages_url, {
        headers: { 'User-Agent': 'GitHub-Stats' }
      });

      if (langRes.ok) {
        const langData = await langRes.json();
        Object.entries(langData).forEach(([lang, bytes]) => {
          languages[lang] = (languages[lang] || 0) + bytes;
        });
      }
    }

    // Calculate percentages & sort
    const total = Object.values(languages).reduce((a, b) => a + b, 0);
    const sorted = Object.entries(languages)
      .map(([lang, bytes]) => ({
        lang,
        percent: ((bytes / total) * 100).toFixed(1)
      }))
      .sort((a, b) => b.percent - a.percent)
      .slice(0, 5); // Top 5

    // Generate SVG
    const colors = {
      JavaScript: '#f1e05a',
      Python: '#3572A5',
      TypeScript: '#3178c6',
      HTML: '#e34c26',
      CSS: '#563d7c',
      Java: '#b07219',
      Go: '#00ADD8',
      Rust: '#ce422b'
    };

    const width = 400;
    const height = 200;
    let y = 30;

    const bars = sorted
      .map(({ lang, percent }, i) => {
        const barWidth = (percent / 100) * 250;
        const color = colors[lang] || '#ccc';
        const yPos = y + i * 30;

        return `
          <text x="10" y="${yPos + 15}" font-size="12" fill="#333">${lang}</text>
          <rect x="80" y="${yPos}" width="${barWidth}" height="18" fill="${color}" rx="3"/>
          <text x="${85 + barWidth}" y="${yPos + 15}" font-size="11" fill="#666">${percent}%</text>
        `;
      })
      .join('');

    const svg = `
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="${width}" height="${height}" fill="#fff"/>
        <text x="10" y="20" font-size="16" font-weight="bold" fill="#000">Top Languages</text>
        ${bars}
      </svg>
    `;

    res.setHeader('Content-Type', 'image/svg+xml');
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.send(svg);
  } catch (err) {
    res.status(400).send(`<svg width="400" height="100"><text x="10" y="50">${err.message}</text></svg>`);
  }
};
