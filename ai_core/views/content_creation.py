import datetime
import logging
import os

import markdown
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView
from groq import Groq

from core.models import LessonPlan

# Setup logging
logger = logging.getLogger(__name__)

# Configure Groq client
groq_client = Groq(api_key=settings.GROQ_API_KEY)


class LessonPlanGeneratorView(LoginRequiredMixin, View):
    template_name = 'ai_core/lesson_plan_generator.html'

    def get(self, request):
        return render(request, self.template_name, {
            'user_role': request.user.role,
        })

    def post(self, request):
        # Check for follow-up request
        follow_up_request = request.POST.get('follow_up_request')
        lesson_plan_id = request.POST.get('lesson_plan_id')

        if follow_up_request and lesson_plan_id:
            # Handle follow-up content generation
            lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id, user=request.user)
            follow_up_content = self.generate_follow_up_content(
                lesson_plan.topic, lesson_plan.level, lesson_plan.area, follow_up_request,
                role=request.user.role
            )
            follow_up_content_html = markdown.markdown(follow_up_content, extensions=['markdown.extensions.tables', 'markdown.extensions.fenced_code'])

            # Append follow-up content to the existing lesson plan with a visual separator
            separator = '<div class="follow-up-separator"><h2>Follow-Up Content</h2></div>'
            combined_content = lesson_plan.content + separator + follow_up_content_html
            lesson_plan.content = combined_content
            lesson_plan.follow_up_count += 1
            lesson_plan.save()

            return render(request, self.template_name, {
                'topic': lesson_plan.topic,
                'level': lesson_plan.level,
                'area': lesson_plan.area,
                'lesson_plan': combined_content,
                'lesson_plan_id': lesson_plan.id,
                'user_role': request.user.role,
            })
        else:
            # Original lesson plan generation
            topic = request.POST.get('topic')
            level = request.POST.get('level')
            area = request.POST.get('area')

            if not topic:
                messages.error(request, "Please enter a topic.")
                return render(request, self.template_name, {
                    'user_role': request.user.role,
                })

            if request.user.role == 'student':
                content = self.generate_study_notes(topic, level, area)
            else:
                content = self.generate_lesson_plan(topic, level, area)

            if content:
                content_html = markdown.markdown(content, extensions=['markdown.extensions.tables', 'markdown.extensions.fenced_code'])
                saved_plan = LessonPlan.objects.create(
                    user=request.user,
                    topic=topic,
                    level=level,
                    area=area,
                    content=content_html
                )

                return render(request, self.template_name, {
                    'topic': topic,
                    'level': level,
                    'area': area,
                    'lesson_plan': content_html,
                    'lesson_plan_id': saved_plan.id,
                    'user_role': request.user.role,
                })
            else:
                messages.error(request, "Failed to generate content. Please try again.")
                return render(request, self.template_name, {
                    'user_role': request.user.role,
                })

    def generate_lesson_plan(self, topic, level, area):
        """Generate a lesson plan using the Groq API tailored for Sierra Leone's education system."""
        try:
            prompt = (
                f"Generate a detailed lesson plan on '{topic}' for {level} students in {area} Sierra Leone. "
                f"Integrate theory with real-life, culturally relevant applications. "
                f"Structure the plan as follows:\n\n"

                f"### 1. Learning Objectives\n"
                f"   - Define clear learning objectives, explaining how this knowledge benefits students in everyday life.\n"
                f"   - Emphasize practical applications in sectors like agriculture, local industries, health, and technology.\n\n"

                f"### 2. Introduction and Theory\n"
                f"   - Provide an accessible overview of the theoretical concepts, using relatable local examples.\n"
                f"   - Integrate storytelling or examples from the local context that connect theory to practice.\n\n"

                f"### 3. Practical Activities and Case Studies\n"
                f"   - Design engaging, hands-on activities that demonstrate real-world applications.\n"
                f"   - Include local case studies showing how these concepts address community challenges.\n"
                f"   - Highlight the work of local industries, organizations, or individuals making a positive impact.\n"
                f"   - Suggest collaborative group exercises or projects that encourage problem-solving and critical thinking.\n\n"

                f"### 4. Lesson Structure and Timings\n"
                f"   - Present the lesson structure as a table with these columns:\n"
                f"     Time Allocation | Activity/Phase | Description | Teaching Method | Resources Needed\n\n"

                f"### 5. Assessment and Reflection\n"
                f"   - Outline assessment methods that measure both theoretical understanding and practical skills.\n"
                f"   - Encourage students to reflect on how they could use the learned concepts in their communities.\n\n"

                f"### 6. Supplementary Resources\n"
                f"   - Recommend additional resources such as relevant books, articles, videos, and local sources.\n"
                f"   - Suggest online resources or workshops that could further enhance understanding.\n\n"

                f"### 7. Community Engagement and Follow-Up Activities\n"
                f"   - Provide suggestions for follow-up projects, like community engagement or field activities.\n"
                f"   - Encourage community experts or guest speakers to share practical insights.\n\n"

                f"### Formatting Instructions\n"
                f"   - For any mathematical expressions, formulas, or equations, use LaTeX notation wrapped in dollar signs.\n"
                f"     Use $...$ for inline math (e.g., $x^2 + y^2 = z^2$) and $$...$$ for display/block math.\n"
                f"   - Include worked examples with step-by-step solutions using LaTeX math notation.\n"
                f"   - Where appropriate, include ONE simple visual diagram using Mermaid syntax in a fenced code block.\n"
                f"     IMPORTANT: Only use simple Mermaid flowcharts (graph TD or graph LR). Keep node labels short and plain-text.\n"
                f"     Do NOT use special characters, LaTeX, parentheses in labels, or quotes inside quotes.\n"
                f"     Example of valid Mermaid syntax:\n"
                f"     ```mermaid\n"
                f"     graph TD\n"
                f"         A[Start] --> B[Step 1]\n"
                f"         B --> C[Step 2]\n"
                f"         C --> D[End]\n"
                f"     ```\n"
            )

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating lesson plan content: {e}")
            return None

    def generate_study_notes(self, topic, level, area):
        """Generate study notes using the Groq API tailored for Sierra Leone's students."""
        try:
            prompt = (
                f"Generate detailed study notes on '{topic}' for {level} students in {area} Sierra Leone. "
                f"The notes should help a student understand and master this topic through clear explanations and practice.\n\n"

                f"### 1. Topic Overview\n"
                f"   - Explain the core concepts in simple, clear language with relatable local examples.\n\n"

                f"### 2. Key Concepts and Definitions\n"
                f"   - List and explain all key terms and definitions the student needs to know.\n\n"

                f"### 3. Detailed Explanations\n"
                f"   - Break down the theory step by step. Use analogies and real-life examples from Sierra Leone.\n\n"

                f"### 4. Worked Examples\n"
                f"   - Provide at least 3 fully worked examples with step-by-step solutions.\n\n"

                f"### 5. Practice Problems\n"
                f"   - Provide 5 practice problems for the student to attempt, ranging from easy to challenging.\n"
                f"   - Include answers at the end.\n\n"

                f"### 6. Summary and Key Takeaways\n"
                f"   - Summarize the most important points in bullet form.\n\n"

                f"### 7. Additional Resources\n"
                f"   - Suggest books, videos, or websites for further study.\n\n"

                f"### Formatting Instructions\n"
                f"   - For any mathematical expressions, formulas, or equations, use LaTeX notation wrapped in dollar signs.\n"
                f"     Use $...$ for inline math (e.g., $x^2 + y^2 = z^2$) and $$...$$ for display/block math.\n"
                f"   - Include worked examples with step-by-step solutions using LaTeX math notation.\n"
                f"   - Where appropriate, include ONE simple visual diagram using Mermaid syntax in a fenced code block.\n"
                f"     IMPORTANT: Only use simple Mermaid flowcharts (graph TD or graph LR). Keep node labels short and plain-text.\n"
                f"     Do NOT use special characters, LaTeX, parentheses in labels, or quotes inside quotes.\n"
                f"     Example of valid Mermaid syntax:\n"
                f"     ```mermaid\n"
                f"     graph TD\n"
                f"         A[Start] --> B[Step 1]\n"
                f"         B --> C[Step 2]\n"
                f"         C --> D[End]\n"
                f"     ```\n"
            )

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating study notes content: {e}")
            return None

    def generate_follow_up_content(self, topic, level, area, follow_up_request, role='teacher'):
        """Generate additional content based on a follow-up request, tailored to the user's role."""
        try:
            if role == 'student':
                role_instruction = (
                    f"You are helping a student study the topic '{topic}' at {level} level in {area} Sierra Leone. "
                    f"Provide additional study material, examples, and explanations as follows:\n"
                )
            else:
                role_instruction = (
                    f"Based on the lesson topic '{topic}' for {level} students in {area} Sierra Leone, "
                    f"provide additional teaching insights, strategies, and classroom activities as follows:\n"
                )

            prompt = (
                f"{role_instruction}"
                f"{follow_up_request}\n"
                f"Ensure the response is tailored to the educational needs and culturally relevant.\n"
                f"For any mathematical expressions or formulas, use LaTeX notation: $...$ for inline math and $$...$$ for display math. "
                f"Where helpful, include ONE simple diagram using a Mermaid flowchart (graph TD) in a fenced code block. "
                f"Keep Mermaid node labels short and plain-text only -- no special characters, LaTeX, or parentheses in labels."
            )
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating follow-up content: {e}")
            return None


@login_required
def download_lesson_plan(request, id):
    """Generate and download the lesson plan as a PDF."""
    lesson_plan = get_object_or_404(LessonPlan, id=id, user=request.user)

    if not lesson_plan.content:
        messages.error(request, "No lesson plan available to download.")
        return redirect('ai_core:lesson_plan_generator')

    # Resolve static path for the logo
    logo_url = request.build_absolute_uri(static('core/images/header_logo.png'))

    # Render HTML with Django template
    lesson_plan_html = render_to_string(
        'ai_core/lesson_plan_pdf.html',
        {
            'lesson_plan_content': lesson_plan.content,
            'generated_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'logo_url': logo_url,
        }
    )

    # Generate PDF with WeasyPrint
    import weasyprint
    pdf = weasyprint.HTML(string=lesson_plan_html, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="lesson_plan.pdf"'
    return response


class LessonPlanListView(LoginRequiredMixin, ListView):
    model = LessonPlan
    template_name = 'ai_core/lesson_plan_list.html'  # Template to display the list of lesson plans
    context_object_name = 'lesson_plans'

    def get_queryset(self):
        # Only return lesson plans created by the current user
        return LessonPlan.objects.filter(user=self.request.user).order_by('-created_at')
